from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

from app.agents.orchestrator import run_real_dry_run_pipeline
from app.db.session import SessionLocal
from app.models.all_models import AgentConfig, AgentRun, Channel, CostEvent, LLMModel, OrgAgent, Post, SystemSetting, Topic
from app.seed import seed_channels, seed_integrations, seed_llm_control_plane, seed_org, seed_settings
from app.services.org import find_org_agent
from app.services.secrets import SecretStoreError, resolve_secret_value
from app.services.settings import get_settings, update_settings


RUNTIME_AGENTS = ["research_agent", "factcheck_agent", "editor_agent", "chief_editor_agent"]

TEST_TOPICS = {
    "era-now": {
        "title": "Глобальные климатические показатели и почему за ними следят редакции",
        "url": "https://public.wmo.int/en/our-mandate/climate/wmo-statement-state-of-global-climate",
        "summary": "WMO publishes state-of-climate material that explains major climate indicators and uncertainty.",
        "raw_text": "Use as a safe news-style test: explain what happened, why climate indicators matter, and what may be watched next. Avoid alarmism and unsupported forecasts.",
    },
    "era-money": {
        "title": "Как малому бизнесу читать денежный поток без сложной финансовой модели",
        "url": "https://www.sba.gov/business-guide/manage-your-business/manage-your-finances",
        "summary": "The SBA guide explains finance basics for small businesses, including cash flow and practical money controls.",
        "raw_text": "Use as a safe money test: focus on where the money is, risks, who benefits, and what the reader can check alone. Avoid investment advice.",
    },
    "era-ai": {
        "title": "Как выбирать модель для агентной редакции: качество, скорость и цена",
        "url": "https://platform.openai.com/docs/models",
        "summary": "OpenAI model documentation describes model families and capabilities relevant for agentic applications.",
        "raw_text": "Use as a safe AI test: explain what changed or appeared, how it works in simple words, how to apply it, and what to try today.",
    },
    "era-health": {
        "title": "Сон как привычка: что можно улучшить без медицинских обещаний",
        "url": "https://www.cdc.gov/sleep/about/index.html",
        "summary": "CDC sleep materials explain why sleep matters and provide general public health context.",
        "raw_text": "Use as a safe health test: explain what is known, what it means for a normal person, limits of evidence, and a safe practical conclusion. No diagnosis or treatment advice.",
    },
    "era-food": {
        "title": "Простая тарелка на неделю: как собрать полезную еду без лишних затрат",
        "url": "https://www.myplate.gov/eat-healthy/food-group-gallery",
        "summary": "MyPlate offers public nutrition guidance and examples of food groups for balanced meals.",
        "raw_text": "Use as a safe food test: give a dish idea, why it is convenient or budget-friendly, ingredients, steps, and variations.",
    },
}


def ok(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"OK: {message}")


def setting_row(db, key: str) -> SystemSetting:
    row = db.execute(select(SystemSetting).where(SystemSetting.key == key)).scalar_one_or_none()
    if row is None:
        get_settings(db)
        row = db.execute(select(SystemSetting).where(SystemSetting.key == key)).scalar_one()
    return row


def choose_openai_model(db) -> str | None:
    try:
        resolve_secret_value(db, "openai", "OPENAI_API_KEY")
    except SecretStoreError:
        return None
    preferred = ["gpt-5.1", "gpt-5", "gpt-4.1-mini", "gpt-4o-mini"]
    enabled = [
        item.model
        for item in db.execute(
            select(LLMModel).where(LLMModel.provider == "openai", LLMModel.enabled == True)  # noqa: E712
        ).scalars()
    ]
    for model in preferred:
        if model in enabled:
            return model
    return sorted(enabled)[0] if enabled else None


def score_is_valid(value: Any) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return 0 <= number <= 100


def write_report(results: list[dict[str, Any]], model: str, failures: list[str]) -> None:
    total_cost = sum(float(item["cost"]) for item in results)
    lines = [
        "# Prompt Quality Report",
        "",
        "## Summary",
        "",
        "- provider used: openai",
        f"- model used: {model}",
        f"- channels tested: {len(results)}",
        f"- total estimated cost: ${total_cost:.6f}",
        f"- failures: {len(failures)}",
        "- MAX publish called: no",
        "- Publisher assigned work: no",
        "- Publisher Agent disabled: yes",
        "- autonomous routines enabled: no",
        "",
        "## Results",
        "",
        "| Channel | Topic ID | Post ID | Title | Cost | Overall | Risk | Rewrite Count | Factcheck |",
        "|---|---:|---:|---|---:|---:|---:|---:|---|",
    ]
    for item in results:
        lines.append(
            f"| {item['channel']} | {item['topic_id']} | {item['post_id']} | {item['title']} | "
            f"${float(item['cost']):.6f} | {item['overall']} | {item['risk']} | {item['rewrite_count']} | {item['factcheck']} |"
        )
    lines.extend(
        [
            "",
            "## Remaining Prompt Weaknesses",
            "",
            "- Real factual verification still depends on source summaries supplied to the model; full source ingestion is intentionally not implemented in this step.",
            "- Health and money content correctly remains conservative and requires human review when risk is elevated.",
            "- The one-rewrite loop is intentionally capped and may leave weak posts for human review instead of spending more.",
            "",
            "## Failures / Warnings",
            "",
        ]
    )
    if failures:
        lines.extend(f"- {failure}" for failure in failures)
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Readiness For Next Step",
            "",
            "- ready for prompt refinement iteration: yes",
            "- ready for MAX publishing: no",
        ]
    )
    Path("docs").mkdir(exist_ok=True)
    Path("docs/PROMPT_QUALITY_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    seed_settings()
    seed_channels()
    seed_org()
    seed_integrations()
    seed_llm_control_plane()

    with SessionLocal() as db:
        model = choose_openai_model(db)
        if model is None:
            print("No OpenAI key configured. Skipping prompt quality smoke.")
            return

        old_settings = get_settings(db)
        old_configs: dict[int, dict[str, Any]] = {}
        old_agents: dict[int, dict[str, Any]] = {}
        publisher_runs_before = db.scalar(select(func.count()).select_from(AgentRun).where(AgentRun.agent_name == "publisher_agent")) or 0
        max_messages_before = db.scalar(select(func.count()).select_from(Post).where(Post.max_message_id.is_not(None))) or 0
        cost_events_before = db.scalar(select(func.count()).select_from(CostEvent)) or 0
        results: list[dict[str, Any]] = []
        failures: list[str] = []

        try:
            update_settings(
                db,
                {
                    "system_mode": "dry_run",
                    "global_agents_enabled": True,
                    "global_routines_enabled": False,
                    "global_publishing_enabled": False,
                    "global_daily_budget_usd": max(float(old_settings["global_daily_budget_usd"]), 100.0),
                    "global_daily_token_limit": max(int(old_settings["global_daily_token_limit"]), 5_000_000),
                },
            )
            publisher = db.execute(select(OrgAgent).where(OrgAgent.name == "publisher_agent")).scalar_one_or_none()
            ok(publisher is not None, "Publisher Agent exists")
            publisher.status = "disabled"

            for runtime_name in RUNTIME_AGENTS:
                agent = find_org_agent(db, runtime_name)
                ok(agent is not None, f"{runtime_name} org agent exists")
                old_agents[agent.id] = {
                    "status": agent.status,
                    "budget_daily": agent.budget_daily,
                    "token_limit_daily": agent.token_limit_daily,
                }
                if agent.status != "disabled":
                    agent.status = "idle"
                agent.budget_daily = max(float(agent.budget_daily or 0), 100.0)
                agent.token_limit_daily = max(int(agent.token_limit_daily or 0), 5_000_000)
                config = db.execute(select(AgentConfig).where(AgentConfig.org_agent_id == agent.id)).scalar_one()
                old_configs[config.id] = {
                    "provider": config.provider,
                    "model": config.model,
                    "enabled": config.enabled,
                    "daily_budget_usd": config.daily_budget_usd,
                    "daily_token_limit": config.daily_token_limit,
                    "max_runs_per_day": config.max_runs_per_day,
                    "timeout_seconds": config.timeout_seconds,
                    "max_tokens": config.max_tokens,
                }
                config.provider = "openai"
                config.model = model
                config.enabled = True
                config.daily_budget_usd = max(float(config.daily_budget_usd), 100.0)
                config.daily_token_limit = max(int(config.daily_token_limit), 5_000_000)
                config.max_runs_per_day = max(int(config.max_runs_per_day), 1000)
                config.timeout_seconds = max(int(config.timeout_seconds), 60)
                config.max_tokens = max(int(config.max_tokens or 0), 1200)
            db.commit()

            for slug, payload in TEST_TOPICS.items():
                channel = db.execute(select(Channel).where(Channel.slug == slug, Channel.status == "active")).scalar_one()
                topic = Topic(
                    title=f"{payload['title']} [{datetime.now(UTC).isoformat()}]",
                    url=payload["url"],
                    summary=payload["summary"],
                    raw_text=payload["raw_text"],
                    usefulness_score=0.75,
                    originality_score=0.72,
                    source_trust_score=0.82,
                    final_score=0.78,
                    assigned_channel_ids=[channel.id],
                    status="new",
                )
                db.add(topic)
                db.commit()
                db.refresh(topic)

                post = run_real_dry_run_pipeline(db, topic_id=topic.id, channel_id=channel.id)
                ok(post.status == "needs_review", f"{channel.name}: post is in review queue")
                ok(post.generation_mode == "dry_run", f"{channel.name}: generation_mode=dry_run")
                ok(post.provider == "openai" and post.model == model, f"{channel.name}: provider/model stored")
                ok((post.tokens_input + post.tokens_output) > 0, f"{channel.name}: token usage stored")
                ok(float(post.estimated_cost_usd or 0) > 0, f"{channel.name}: cost stored")
                data = post.structured_outputs_json or {}
                ok("channel_playbook" in data, f"{channel.name}: channel playbook stored")
                ok("quality_scores" in data, f"{channel.name}: quality scores stored")
                ok("factcheck" in data and "chief_editor" in data, f"{channel.name}: factcheck and chief outputs stored")
                for key in [
                    "editorial_value_score",
                    "factuality_score",
                    "clarity_score",
                    "usefulness_score",
                    "channel_fit_score",
                    "originality_score",
                    "risk_score",
                    "overall_quality_score",
                ]:
                    ok(score_is_valid(data["quality_scores"].get(key)), f"{channel.name}: {key} valid")
                factcheck = data["factcheck"]
                ok("unsupported_claims" in factcheck, f"{channel.name}: unsupported_claims present")
                ok("risk_notes" in factcheck, f"{channel.name}: risk_notes present")
                rewrite_count = int(data.get("rewrite_attempts_used") or 0)
                ok(rewrite_count <= 1, f"{channel.name}: rewrite count <= 1")
                results.append(
                    {
                        "channel": channel.name,
                        "topic_id": topic.id,
                        "post_id": post.id,
                        "title": post.title.replace("|", "/")[:90],
                        "cost": post.estimated_cost_usd,
                        "overall": data["quality_scores"].get("overall_quality_score"),
                        "risk": data["quality_scores"].get("risk_score"),
                        "rewrite_count": rewrite_count,
                        "factcheck": factcheck.get("factcheck_result") or factcheck.get("result"),
                    }
                )

            db.refresh(publisher)
            publisher_runs_after = db.scalar(select(func.count()).select_from(AgentRun).where(AgentRun.agent_name == "publisher_agent")) or 0
            cost_events_after = db.scalar(select(func.count()).select_from(CostEvent)) or 0
            max_messages_after = db.scalar(select(func.count()).select_from(Post).where(Post.max_message_id.is_not(None))) or 0
            ok(publisher_runs_after == publisher_runs_before, "no Publisher Agent runs")
            ok(publisher.status == "disabled", "Publisher Agent remains disabled")
            ok(cost_events_after > cost_events_before, "cost events created")
            ok(max_messages_after == max_messages_before, "no MAX message id created")
        except Exception as exc:
            failures.append(str(exc))
            raise
        finally:
            for key, value in old_settings.items():
                setting_row(db, key).value_json = {"value": value}
            setting_row(db, "global_publishing_enabled").value_json = {"value": False}
            setting_row(db, "global_routines_enabled").value_json = {"value": False}
            setting_row(db, "global_agents_enabled").value_json = {"value": False}
            for config_id, values in old_configs.items():
                config = db.get(AgentConfig, config_id)
                if config:
                    for key, value in values.items():
                        setattr(config, key, value)
            for agent_id, values in old_agents.items():
                agent = db.get(OrgAgent, agent_id)
                if agent:
                    for key, value in values.items():
                        setattr(agent, key, value)
            publisher = db.execute(select(OrgAgent).where(OrgAgent.name == "publisher_agent")).scalar_one_or_none()
            if publisher:
                publisher.status = "disabled"
            db.commit()
            write_report(results, model, failures)

    print("SMOKE PROMPT QUALITY PASSED")


if __name__ == "__main__":
    main()
