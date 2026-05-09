from datetime import UTC, datetime

from sqlalchemy import func, select

from app.agents.orchestrator import run_real_dry_run_pipeline
from app.db.session import SessionLocal
from app.models.all_models import AgentConfig, AgentRun, Channel, CostEvent, Integration, LLMModel, OrgAgent, Post, SystemSetting, Topic
from app.seed import seed_channels, seed_integrations, seed_llm_control_plane, seed_org, seed_settings
from app.services.org import find_org_agent
from app.services.secrets import SecretStoreError, resolve_secret_value
from app.services.settings import get_settings, update_settings


PROVIDERS = [
    ("openai", "OPENAI_API_KEY", "gpt-4.1-mini"),
    ("anthropic", "ANTHROPIC_API_KEY", "claude-3-5-haiku-latest"),
    ("gemini", "GEMINI_API_KEY", "gemini-2.5-flash"),
]
RUNTIME_AGENTS = ["research_agent", "factcheck_agent", "editor_agent", "chief_editor_agent"]


def ok(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"OK: {message}")


def choose_provider(db) -> tuple[str, str] | None:
    for provider, env_name, model in PROVIDERS:
        try:
            resolve_secret_value(db, provider, env_name)
        except SecretStoreError:
            continue
        integration = db.execute(select(Integration).where(Integration.provider == provider)).scalars().first()
        configured_model = (integration.config_json or {}).get("model") if integration else None
        candidates = [configured_model, model]
        enabled_models = {
            item.model
            for item in db.execute(
                select(LLMModel).where(LLMModel.provider == provider, LLMModel.enabled == True)  # noqa: E712
            ).scalars()
        }
        for candidate in candidates:
            if candidate and candidate in enabled_models:
                return provider, candidate
        if enabled_models:
            return provider, sorted(enabled_models)[0]
    return None


def setting_row(db, key: str) -> SystemSetting:
    row = db.execute(select(SystemSetting).where(SystemSetting.key == key)).scalar_one_or_none()
    if row is None:
        get_settings(db)
        row = db.execute(select(SystemSetting).where(SystemSetting.key == key)).scalar_one()
    return row


def main() -> None:
    seed_settings()
    seed_channels()
    seed_org()
    seed_integrations()
    seed_llm_control_plane()

    with SessionLocal() as db:
        selected = choose_provider(db)
        if selected is None:
            print("No real provider key configured. Skipping real LLM dry-run.")
            return
        provider, model = selected
        old_settings = get_settings(db)
        old_configs: dict[int, dict] = {}
        old_agents: dict[int, dict] = {}
        try:
            update_settings(
                db,
                {
                    "system_mode": "dry_run",
                    "global_agents_enabled": True,
                    "global_routines_enabled": False,
                    "global_publishing_enabled": False,
                    "global_daily_budget_usd": max(float(old_settings["global_daily_budget_usd"]), 100.0),
                    "global_daily_token_limit": max(int(old_settings["global_daily_token_limit"]), 5000000),
                },
            )
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
                agent.token_limit_daily = max(int(agent.token_limit_daily or 0), 5000000)
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
                config.provider = provider
                config.model = model
                config.enabled = True
                config.daily_budget_usd = max(float(config.daily_budget_usd), 100.0)
                config.daily_token_limit = max(int(config.daily_token_limit), 5000000)
                config.max_runs_per_day = max(int(config.max_runs_per_day), 1000)
                config.timeout_seconds = max(int(config.timeout_seconds), 45)
            db.commit()

            channel = db.execute(
                select(Channel).where(Channel.slug == "era-ai", Channel.status == "active")
            ).scalars().first() or db.execute(select(Channel).where(Channel.status == "active").order_by(Channel.id)).scalars().first()
            ok(channel is not None, "active channel exists")
            topic = Topic(
                title=f"Smoke real LLM dry-run {datetime.now(UTC).isoformat()}",
                url="https://developers.openai.com/api/docs/models",
                summary="OpenAI model documentation lists current GPT models, model IDs, structured output support through the Responses API, and pricing-relevant model choices for builders.",
                raw_text=(
                    "Source-backed editorial test: OpenAI's official API model documentation describes current model families, "
                    "including flagship and lower-latency options. ERA AI readers need a cautious practical note about choosing "
                    "a model for agentic editorial workflows, with human review required before publication."
                ),
                usefulness_score=0.7,
                originality_score=0.7,
                source_trust_score=0.8,
                final_score=0.75,
                status="new",
            )
            db.add(topic)
            db.commit()
            db.refresh(topic)

            post = run_real_dry_run_pipeline(db, topic_id=topic.id, channel_id=channel.id)
            ok(post.status == "needs_review", "dry-run post is in review queue")
            ok(post.generation_mode == "dry_run", "post generation_mode=dry_run")
            ok(not post.publishable and not post.mock_only, "dry-run post is not public-publishable and not mock")
            ok(post.provider == provider and post.model == model, "post stores provider/model")
            ok((post.tokens_input + post.tokens_output) > 0, "post stores token usage")

            runs = db.execute(select(AgentRun).where(AgentRun.input_json["topic_id"].as_integer() == topic.id)).scalars().all()
            ok(len(runs) >= 4, "agent_runs created")
            ok(all(run.provider == provider for run in runs), "agent_runs store real provider")
            costs = db.scalar(select(CostEvent).where(CostEvent.provider == provider).order_by(CostEvent.id.desc()))
            ok(costs is not None, "cost_event created")
            publisher_runs = db.scalar(select(func.count()).select_from(AgentRun).where(AgentRun.agent_name == "publisher_agent")) or 0
            ok(publisher_runs == 0, "no publisher run")
        finally:
            for key, value in old_settings.items():
                setting_row(db, key).value_json = {"value": value}
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
            db.commit()

    print("SMOKE REAL LLM DRY-RUN PASSED")


if __name__ == "__main__":
    main()
