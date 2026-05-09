from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

from app.agents.orchestrator import run_real_dry_run_pipeline
from app.db.session import SessionLocal
from app.models.all_models import AgentConfig, AgentRun, Channel, CostEvent, OrgAgent, Source, SourceChannelMap, SourceItem, SystemSetting, Topic
from app.seed import seed_channels, seed_integrations, seed_llm_control_plane, seed_org, seed_settings
from app.services.org import find_org_agent
from app.services.secrets import SecretStoreError, resolve_secret_value
from app.services.settings import get_settings, update_settings
from app.services.source_ingestion import SourceFetchService

RUNTIME_AGENTS = ["research_agent", "factcheck_agent", "editor_agent", "chief_editor_agent"]
RSS_URL = "https://www.nasa.gov/rss/dyn/breaking_news.rss"
WEBSITE_URL = "https://www.cdc.gov/sleep/about/index.html"


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


def openai_available(db) -> bool:
    try:
        resolve_secret_value(db, "openai", "OPENAI_API_KEY")
        return True
    except SecretStoreError:
        return False


def report(lines: list[str]) -> None:
    Path("docs").mkdir(exist_ok=True)
    Path("docs/SOURCE_INGESTION_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def source_by_name(db, name: str, url: str, type_: str, channel: Channel) -> Source:
    source = db.execute(select(Source).where(Source.name == name)).scalar_one_or_none()
    if source is None:
        source = Source(name=name, url=url, type=type_, language="en", trust_score=0.85, status="active")
        db.add(source)
        db.flush()
    source.url = url
    source.type = type_
    source.status = "active"
    source.trust_score = 0.85
    source.language = "en"
    mapping = db.execute(select(SourceChannelMap).where(SourceChannelMap.source_id == source.id, SourceChannelMap.channel_id == channel.id)).scalar_one_or_none()
    if mapping is None:
        db.add(SourceChannelMap(source_id=source.id, channel_id=channel.id, relevance_weight=1.0, enabled=True))
    db.commit()
    db.refresh(source)
    return source


def main() -> None:
    seed_settings()
    seed_channels()
    seed_org()
    seed_integrations()
    seed_llm_control_plane()

    with SessionLocal() as db:
        ai_channel = db.execute(select(Channel).where(Channel.slug == "era-ai")).scalar_one()
        health_channel = db.execute(select(Channel).where(Channel.slug == "era-health")).scalar_one()
        rss_source = source_by_name(db, "Smoke NASA RSS public source", RSS_URL, "rss", ai_channel)
        website_source = source_by_name(db, "Smoke CDC Sleep public page", WEBSITE_URL, "website", health_channel)
        service = SourceFetchService()

        rss_before_topics = db.scalar(select(func.count()).select_from(Topic).where(Topic.source_id == rss_source.id)) or 0
        rss_result = service.fetch_source(db, rss_source, limit=1, create_topics=True)
        ok(rss_result.fetched_count >= 1, "RSS source fetch works")
        ok(rss_result.source_item_ids, "RSS source item stored")
        rss_item = db.get(SourceItem, rss_result.source_item_ids[0])
        ok(rss_item is not None and rss_item.content_length > 0, "RSS item has extracted content or extraction status")

        website_result = service.fetch_source(db, website_source, limit=1, create_topics=True)
        ok(website_result.fetched_count == 1, "public URL fetch works")
        ok(website_result.source_item_ids, "website source item stored")
        website_item = db.get(SourceItem, website_result.source_item_ids[0])
        ok(website_item is not None, "website source item exists")
        ok(website_item.extraction_status in {"extracted", "too_short", "blocked", "duplicate"}, "website extraction status is explicit")
        ok(not website_item.paywall_or_blocked_detected or website_item.extraction_status == "blocked", "blocked pages are marked")

        ready_topic = db.execute(
            select(Topic)
            .where(Topic.source_id.in_([rss_source.id, website_source.id]), Topic.status == "ready_for_dry_run")
            .order_by(Topic.id.desc())
        ).scalars().first()
        ok(ready_topic is not None, "source item creates ready_for_dry_run topic")
        ok(ready_topic.source_item_id is not None, "topic links to source_item")
        ok(ready_topic.raw_text and ready_topic.content_length > 0, "topic stores extracted text")
        ok(ready_topic.final_score > 0, "topic scored without LLM")

        second = service.fetch_source(db, rss_source, limit=1, create_topics=True)
        rss_after_topics = db.scalar(select(func.count()).select_from(Topic).where(Topic.source_id == rss_source.id)) or 0
        ok(second.duplicates >= 1 or rss_after_topics == rss_before_topics + rss_result.topics_created, "second ingestion detects duplicates")
        ok(rss_after_topics <= rss_before_topics + rss_result.topics_created + 1, "second ingestion does not create duplicate topic batch")

        old_settings = get_settings(db)
        old_configs: dict[int, dict[str, Any]] = {}
        old_agents: dict[int, dict[str, Any]] = {}
        dry_run_status = "skipped: no OpenAI key"
        dry_run_post_id: int | None = None
        publisher_runs_before = db.scalar(select(func.count()).select_from(AgentRun).where(AgentRun.agent_name == "publisher_agent")) or 0
        try:
            if openai_available(db):
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
                post = run_real_dry_run_pipeline(db, topic_id=ready_topic.id, channel_id=(ready_topic.assigned_channel_ids or [ai_channel.id])[0])
                ok(post.status == "needs_review", "dry-run post from ingested topic is in review queue")
                ok(post.generation_mode == "dry_run", "dry-run post generation mode is dry_run")
                dry_run_status = "passed"
                dry_run_post_id = post.id
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

        publisher_runs_after = db.scalar(select(func.count()).select_from(AgentRun).where(AgentRun.agent_name == "publisher_agent")) or 0
        ok(publisher_runs_after == publisher_runs_before, "Publisher Agent received no work")
        ok(db.scalar(select(func.count()).select_from(CostEvent)) is not None, "cost table reachable")

        report(
            [
                "# Source Ingestion Report",
                "",
                "## Summary",
                "",
                "- source types implemented: rss, website, manual_url, api_placeholder, ladder_optional disabled",
                f"- smoke RSS source used: {RSS_URL}",
                f"- smoke public URL used: {WEBSITE_URL}",
                f"- RSS items fetched: {rss_result.fetched_count}",
                f"- RSS topics created: {rss_result.topics_created}",
                f"- duplicate items on second run: {second.duplicates}",
                f"- website extraction status: {website_item.extraction_status}",
                f"- dry-run generation from ingested topic: {dry_run_status}",
                f"- dry-run post id: {dry_run_post_id or 'n/a'}",
                "- MAX publish called: no",
                "- Publisher assigned work: no",
                "",
                "## Extraction Quality Notes",
                "",
                "- Extraction removes script/style/navigation/header/footer-like blocks and keeps headings, paragraphs, lists and blockquotes.",
                "- Pages with login/paywall/subscription markers are marked blocked and are not used as ready topics.",
                "- Full source text is stored for internal analysis; generated posts must summarize with added value and must not republish large article fragments.",
                "",
                "## Safety Notes",
                "",
                "- Ladder optional remains disabled by default.",
                "- No paywall bypass is implemented.",
                "- No MAX publishing is implemented.",
                "- Publisher Agent remains disabled.",
                "",
                "## Next Step Recommendation",
                "",
                "- Improve source-specific extraction heuristics and add operator curation before any autonomous discovery.",
            ]
        )

    print("SMOKE SOURCE INGESTION PASSED")


if __name__ == "__main__":
    main()
