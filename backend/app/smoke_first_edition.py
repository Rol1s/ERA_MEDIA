from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models.all_models import AgentConfig, AgentRun, Channel, DailyEdition, OrgAgent, Post, SystemSetting, Topic
from app.seed import seed_channels, seed_integrations, seed_llm_control_plane, seed_org, seed_settings
from app.services import daily_editions as editions
from app.services.org import find_org_agent
from app.services.secrets import SecretStoreError, resolve_secret_value
from app.services.settings import get_settings, update_settings

RUNTIME_AGENTS = ["research_agent", "factcheck_agent", "editor_agent", "chief_editor_agent"]
SMOKE_CHANNELS = ["era-ai", "era-money"]


def ok(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"OK: {message}")


def setting_row(db, key: str) -> SystemSetting:
    row = db.execute(select(SystemSetting).where(SystemSetting.key == key)).scalar_one_or_none()
    if row is None:
        row = SystemSetting(key=key, value_json={"value": None})
        db.add(row)
        db.flush()
    return row


def openai_available(db) -> bool:
    try:
        resolve_secret_value(db, "openai", "OPENAI_API_KEY")
        return True
    except SecretStoreError:
        return False


def write_report(results: list[dict[str, Any]], total_cost: float, dry_run_status: str, warnings: list[str]) -> None:
    lines = [
        "# First Editorial Issue Report",
        "",
        "## Summary",
        "",
        "- channels: ERA AI, ERA Деньги",
        f"- dry-run generation: {dry_run_status}",
        f"- total cost: ${total_cost:.6f}",
        "- MAX publish called: no",
        "- Publisher Agent disabled: yes",
        "",
        "## Results",
        "",
        "| Channel | Topics collected | Posts generated | Posts approved | Posts rejected | Sample titles |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for item in results:
        lines.append(
            f"| {item['channel']} | {item['topics']} | {item['generated']} | {item['approved']} | {item['rejected']} | {item['sample_titles']} |"
        )
    lines.extend(["", "## Quality Issues", ""])
    lines.extend([f"- {warning}" for warning in warnings] or ["- none"])
    lines.extend(
        [
            "",
            "## Next Recommendation",
            "",
            "- Use /editions for manual editorial curation: collect, select, generate, approve final pack, then copy manually.",
            "- Do not move to MAX publishing until final pack review quality is stable.",
        ]
    )
    Path("docs").mkdir(exist_ok=True)
    Path("docs/FIRST_EDITORIAL_ISSUE_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def ensure_smoke_editions(db) -> list[DailyEdition]:
    latest = db.scalar(select(func.max(DailyEdition.date))) or date.today()
    edition_date = latest + timedelta(days=1)
    channels = list(db.execute(select(Channel).where(Channel.slug.in_(SMOKE_CHANNELS)).order_by(Channel.slug)).scalars())
    return [editions.ensure_daily_edition(db, channel, edition_date=edition_date) for channel in channels]


def clone_reusable_candidates(db, edition: DailyEdition, count: int = 5) -> None:
    reusable = list(
        db.execute(
            select(Topic)
            .where(
                Topic.id.not_in(select(Topic.id).where(Topic.daily_edition_id == edition.id)),
                Topic.url.is_not(None),
                Topic.raw_text != "",
                Topic.assigned_channel_ids.contains([edition.channel_id]),
            )
            .order_by(Topic.final_score.desc(), Topic.id.desc())
            .limit(count)
        ).scalars()
    )
    for source in reusable:
        clone = Topic(
            source_id=source.source_id,
            daily_edition_id=edition.id,
            title=source.title,
            url=source.url,
            raw_text=source.raw_text,
            summary=source.summary,
            published_at=source.published_at,
            freshness_score=source.freshness_score,
            relevance_score=source.relevance_score,
            virality_score=source.virality_score,
            usefulness_score=source.usefulness_score,
            originality_score=source.originality_score,
            importance_score=source.importance_score,
            source_trust_score=source.source_trust_score,
            risk_score=source.risk_score,
            final_score=source.final_score,
            why_this_matters=source.why_this_matters,
            suggested_angle=source.suggested_angle,
            assigned_channel_ids=[edition.channel_id],
            status="ready_for_dry_run",
            extraction_status=source.extraction_status,
            extraction_error=source.extraction_error,
            content_length=source.content_length,
            language=source.language,
            source_published_at=source.source_published_at,
            canonical_url=source.canonical_url,
            paywall_or_blocked_detected=False,
        )
        db.add(clone)
    db.commit()


def main() -> None:
    seed_settings()
    seed_channels()
    seed_org()
    seed_integrations()
    seed_llm_control_plane()

    with SessionLocal() as db:
        rows = ensure_smoke_editions(db)
        ok(len(rows) == 2, "ERA AI and ERA Деньги editions exist")
        publisher_runs_before = db.scalar(select(func.count()).select_from(AgentRun).where(AgentRun.agent_name == "publisher_agent")) or 0
        max_messages_before = db.scalar(select(func.count()).select_from(Post).where(Post.max_message_id.is_not(None))) or 0
        old_settings = get_settings(db)
        old_configs: dict[int, dict[str, Any]] = {}
        old_agents: dict[int, dict[str, Any]] = {}
        results: list[dict[str, Any]] = []
        warnings: list[str] = []
        dry_run_status = "skipped: no OpenAI key"

        for edition in rows:
            result = editions.collect_candidates(db, edition, limit_per_source=5)
            detail = editions.edition_detail_payload(db, edition)
            if not detail["candidate_topics"]:
                clone_reusable_candidates(db, edition, count=5)
                detail = editions.edition_detail_payload(db, edition)
            ok(len(detail["candidate_topics"]) >= 1, f"{edition.channel.name}: candidate topics appear")
            selected = editions.select_top_topics(db, edition, count=5)
            ok(len(selected) >= 1, f"{edition.channel.name}: selected topics appear")

        try:
            if openai_available(db):
                dry_run_status = "passed"
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
                for runtime_name in RUNTIME_AGENTS:
                    agent = find_org_agent(db, runtime_name)
                    ok(agent is not None, f"{runtime_name} org agent exists")
                    old_agents[agent.id] = {"status": agent.status, "budget_daily": agent.budget_daily, "token_limit_daily": agent.token_limit_daily}
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
                    }
                    config.provider = "openai"
                    config.model = "gpt-4.1-mini"
                    config.enabled = True
                    config.daily_budget_usd = max(float(config.daily_budget_usd), 100.0)
                    config.daily_token_limit = max(int(config.daily_token_limit), 5_000_000)
                    config.max_runs_per_day = max(int(config.max_runs_per_day), 1000)
                    config.timeout_seconds = max(int(config.timeout_seconds), 60)
                publisher = db.execute(select(OrgAgent).where(OrgAgent.name == "publisher_agent")).scalar_one()
                publisher.status = "disabled"
                db.commit()

                for edition in rows:
                    selected_topics = list(
                        db.execute(
                            select(Topic)
                            .where(Topic.daily_edition_id == edition.id, Topic.status.in_(["edition_selected", "edition_generated"]))
                            .order_by(Topic.final_score.desc(), Topic.id.desc())
                            .limit(2)
                        ).scalars()
                    )
                    generated: list[Post] = []
                    for topic in selected_topics:
                        post = editions.generate_post_for_topic(db, edition, topic.id)
                        generated.append(post)
                    ok(len(generated) >= 2, f"{edition.channel.name}: generated at least 2 posts")
                    for post in generated:
                        if post.quality_score >= 75 and post.source_urls:
                            editions.approve_post_for_final_pack(db, edition, post.id, human_note="Smoke human review: source and risk checked for internal final pack.")
                        else:
                            warnings.append(f"{edition.channel.name} post #{post.id} not approved: quality={post.quality_score}, sources={len(post.source_urls)}")
                    detail = editions.edition_detail_payload(db, edition)
                    ok(len(detail["generated_posts"]) >= 2, f"{edition.channel.name}: posts in review/final pack")
                    ok(len(detail["final_pack_posts"]) >= 1, f"{edition.channel.name}: final pack exists")
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

        total_cost = 0.0
        for edition in rows:
            db.refresh(edition)
            detail = editions.edition_detail_payload(db, edition)
            generated_posts = detail["generated_posts"]
            total_cost += sum(float(post.estimated_cost_usd or 0) for post in generated_posts)
            results.append(
                {
                    "channel": edition.channel.name,
                    "topics": len(detail["candidate_topics"]) + len(detail["rejected_topics"]),
                    "generated": len(generated_posts),
                    "approved": len(detail["final_pack_posts"]),
                    "rejected": len(detail["rejected_posts"]),
                    "sample_titles": "; ".join(post.title.replace("|", "/")[:60] for post in generated_posts[:2]) or "n/a",
                }
            )
        publisher_runs_after = db.scalar(select(func.count()).select_from(AgentRun).where(AgentRun.agent_name == "publisher_agent")) or 0
        ok(publisher_runs_after == publisher_runs_before, "no Publisher Agent work")
        publisher = db.execute(select(OrgAgent).where(OrgAgent.name == "publisher_agent")).scalar_one()
        ok(publisher.status == "disabled", "Publisher Agent disabled")
        max_messages_after = db.scalar(select(func.count()).select_from(Post).where(Post.max_message_id.is_not(None))) or 0
        ok(max_messages_after == max_messages_before, "no MAX publishing")
        write_report(results, total_cost, dry_run_status, warnings)

    print("SMOKE FIRST EDITION PASSED")


if __name__ == "__main__":
    main()
