from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agents.llm_provider import LLMProvider, provider_for_name
from app.models.all_models import AgentConfig, AgentRun, OrgAgent, PromptTemplate
from app.services.org import daily_agent_usage, find_org_agent, today_start
from app.services.secrets import PROVIDER_SECRET_NAMES, resolve_secret_value
from app.services.settings import get_setting


def get_agent_config(db: Session, runtime_agent_name: str, *, manual_override: bool = False) -> tuple[OrgAgent, AgentConfig, PromptTemplate | None]:
    agent = find_org_agent(db, runtime_agent_name)
    if agent is None:
        raise RuntimeError(f"Org agent is missing for runtime agent: {runtime_agent_name}")
    config = db.execute(select(AgentConfig).where(AgentConfig.org_agent_id == agent.id)).scalar_one_or_none()
    if config is None:
        raise RuntimeError(f"Agent config is missing for {agent.title}")
    if not config.enabled and not manual_override:
        raise RuntimeError(f"Agent config is disabled for {agent.title}")
    prompt = resolve_prompt_template(db, agent, config)
    return agent, config, prompt


def resolve_prompt_template(db: Session, agent: OrgAgent, config: AgentConfig) -> PromptTemplate | None:
    if config.prompt_template_id:
        prompt = db.get(PromptTemplate, config.prompt_template_id)
        if prompt:
            return prompt
    return db.execute(
        select(PromptTemplate)
        .where(PromptTemplate.agent_type == agent.role, PromptTemplate.status == "active")
        .order_by(PromptTemplate.version.desc(), PromptTemplate.id.desc())
    ).scalar_one_or_none()


def provider_for_agent(db: Session, runtime_agent_name: str, *, manual_override: bool = False) -> LLMProvider:
    _, config, _ = get_agent_config(db, runtime_agent_name, manual_override=manual_override)
    system_mode = str(get_setting(db, "system_mode"))
    provider_name = "mock" if system_mode == "mock" else config.provider
    model = "mock" if provider_name == "mock" else config.model
    api_key = None
    if provider_name in PROVIDER_SECRET_NAMES and provider_name != "mock":
        api_key = resolve_secret_value(db, provider_name, PROVIDER_SECRET_NAMES[provider_name])
    return provider_for_name(provider_name, model=model, temperature=config.temperature, max_tokens=config.max_tokens, api_key=api_key)


def daily_agent_config_runs(db: Session, agent: OrgAgent) -> int:
    start = today_start()
    runtime_names = [agent.name]
    role_map = {
        "world_scout_agent": ["research_agent"],
        "factcheck_agent": ["factcheck_agent"],
        "editor_in_chief": ["editor_agent", "chief_editor_agent"],
    }
    runtime_names.extend(role_map.get(agent.name, []))
    return int(db.scalar(select(func.count()).select_from(AgentRun).where(AgentRun.agent_name.in_(runtime_names), AgentRun.started_at >= start)) or 0)


def enforce_agent_config_limits(db: Session, agent: OrgAgent, config: AgentConfig, *, manual_override: bool = False) -> None:
    if manual_override:
        return
    if daily_agent_config_runs(db, agent) >= config.max_runs_per_day:
        raise RuntimeError(f"{agent.title} reached max runs per day")
    usage = daily_agent_usage(db, agent.id)
    if config.daily_budget_usd > 0 and float(usage["cost"]) >= config.daily_budget_usd:
        raise RuntimeError(f"{agent.title} reached agent config daily budget")
    if config.daily_token_limit > 0 and int(usage["tokens"]) >= config.daily_token_limit:
        raise RuntimeError(f"{agent.title} reached agent config daily token limit")


def render_prompt(template: PromptTemplate | None, fallback: str, variables: dict[str, Any]) -> str:
    content = template.content if template else fallback
    for key, value in variables.items():
        content = content.replace("{{" + key + "}}", str(value))
    return content


def prompt_metadata(prompt: PromptTemplate | None, config: AgentConfig) -> dict[str, Any]:
    return {
        "provider": config.provider,
        "model": config.model,
        "prompt_template_id": prompt.id if prompt else None,
        "prompt_version": prompt.version if prompt else None,
        "agent_config_id": config.id,
        "timeout_seconds": config.timeout_seconds,
    }
