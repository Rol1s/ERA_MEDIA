from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.contracts import (
    CHIEF_EDITOR_AGENT,
    EDITOR_AGENT,
    FACTCHECK_AGENT,
    RESEARCH_AGENT,
    REWRITE_AGENT,
    AgentSpec,
    ChiefEditorInput,
    ChiefEditorOutput,
    EditorInput,
    EditorOutput,
    FactcheckInput,
    FactcheckOutput,
    ResearchInput,
    ResearchOutput,
)
from app.agents.llm_provider import LLMProvider, LLMResponse, LLMUsage, MockLLMProvider
from app.models.all_models import AgentRun, Channel, LLMModel, Post, SourceChannelMap, Task, Topic
from app.services.control_plane import create_issue_for_pipeline, log_decision, update_issue
from app.services.editorial_playbooks import channel_playbook, playbook_summary
from app.services.llm_config import enforce_agent_config_limits, get_agent_config, provider_for_agent, render_prompt
from app.services.notifications import create_notification
from app.services.org import create_cost_event_for_run, ensure_agent_budget, find_org_agent, log_activity
from app.services.settings import ensure_global_agents_enabled, get_setting

TERMINAL_AGENT_STATES = {
    "completed",
    "completed_with_warnings",
    "failed",
    "cancelled",
    "waiting_human",
    "rejected",
    "scheduled",
    "published",
}


class PipelineError(Exception):
    pass


class PipelineRejected(PipelineError):
    pass


def now_utc() -> datetime:
    return datetime.now(UTC)


def _model_dump(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(mode="json")


def _strict_json_schema(model: type[BaseModel]) -> dict[str, Any]:
    schema = model.model_json_schema()

    def visit(node: Any) -> Any:
        if isinstance(node, dict):
            if node.get("type") == "object":
                props = node.get("properties") or {}
                for prop_name, prop_schema in list(props.items()):
                    if (
                        isinstance(prop_schema, dict)
                        and prop_schema.get("type") == "object"
                        and not prop_schema.get("properties")
                        and prop_schema.get("additionalProperties") is not None
                    ):
                        props.pop(prop_name)
                node["additionalProperties"] = False
                node["required"] = list(props.keys())
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for item in node:
                visit(item)
        return node

    return visit(schema)


def _estimate_llm_cost(db: Session, provider: str, model: str, tokens_input: int, tokens_output: int) -> float:
    row = db.execute(select(LLMModel).where(LLMModel.provider == provider, LLMModel.model == model)).scalar_one_or_none()
    if row is None:
        return 0.0
    return round((tokens_input / 1_000_000 * row.input_cost_per_1m) + (tokens_output / 1_000_000 * row.output_cost_per_1m), 8)


def _llm_structured_output(
    db: Session,
    *,
    spec: AgentSpec,
    agent_input: BaseModel,
    manual_override: bool,
    fallback_system: str,
) -> tuple[BaseModel, LLMResponse]:
    _agent, config, prompt_template = get_agent_config(db, spec.name, manual_override=manual_override)
    provider = provider_for_agent(db, spec.name, manual_override=manual_override)
    system_prompt = config.system_prompt or fallback_system
    rendered = render_prompt(
        prompt_template,
        fallback_system,
        {
            "channel": getattr(agent_input, "channel_name", ""),
            "topic": getattr(agent_input, "topic_title", ""),
            "channel_playbook": getattr(agent_input, "channel_playbook", {}),
            "playbook": getattr(agent_input, "channel_playbook", {}),
        },
    )
    user_prompt = (
        f"{rendered}\n\n"
        "Return only valid JSON matching the provided schema. Do not include markdown.\n\n"
        "For normal dry-run editorial generation, set status to completed. Use risk fields, "
        "requires_human_review, required_changes, or decision=waiting_human for caution instead of status=rejected. "
        "Use the channel_playbook to shape structure, tone, banned patterns, and quality gates. "
        "All quality and risk score fields are 0-100.\n\n"
        f"Input JSON:\n{agent_input.model_dump_json()}"
    )
    last_error: Exception | None = None
    for attempt in range(2):
        prompt = user_prompt if attempt == 0 else (
            f"{user_prompt}\n\nPrevious response was invalid for this schema: {last_error}. "
            "Correct it and return only schema-valid JSON."
        )
        try:
            response = provider.generate_structured(
                system_prompt=system_prompt,
                user_prompt=prompt,
                output_schema=_strict_json_schema(spec.output_schema),
                model=provider.model,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
                tools=config.tools_json,
                timeout_seconds=config.timeout_seconds,
            )
            if response.usage.estimated_cost <= 0 and (response.usage.tokens_input or response.usage.tokens_output):
                estimated_cost = _estimate_llm_cost(
                    db,
                    response.provider,
                    response.model,
                    response.usage.tokens_input,
                    response.usage.tokens_output,
                )
                response = LLMResponse(
                    text=response.text,
                    usage=LLMUsage(
                        tokens_input=response.usage.tokens_input,
                        tokens_output=response.usage.tokens_output,
                        estimated_cost=estimated_cost,
                    ),
                    provider=response.provider,
                    model=response.model,
                    structured=response.structured,
                )
            validated = spec.output_schema.model_validate(response.structured or {})
            if hasattr(validated, "tokens_input"):
                setattr(validated, "tokens_input", response.usage.tokens_input)
            if hasattr(validated, "tokens_output"):
                setattr(validated, "tokens_output", response.usage.tokens_output)
            if hasattr(validated, "estimated_cost"):
                setattr(validated, "estimated_cost", response.usage.estimated_cost)
            return validated, response
        except Exception as exc:
            last_error = exc
    raise PipelineError(f"{spec.name} returned invalid JSON after retry: {last_error}")


def _run_agent(
    db: Session,
    *,
    spec: AgentSpec,
    agent_input: BaseModel,
    handler: Callable[[], BaseModel],
    task: Task | None = None,
    manual_override: bool = False,
) -> BaseModel:
    last_error: str | None = None
    org_agent = find_org_agent(db, spec.name)
    ensure_global_agents_enabled(db, manual_override=manual_override)
    _config_agent, agent_config, prompt_template = get_agent_config(db, spec.name, manual_override=manual_override)
    effective_provider = "mock" if get_setting(db, "system_mode") == "mock" else agent_config.provider
    effective_model = "mock" if effective_provider == "mock" else agent_config.model
    ensure_agent_budget(
        db,
        org_agent,
        manual_override=manual_override,
        enforce_spend_limit=effective_provider != "mock",
    )
    enforce_agent_config_limits(
        db,
        _config_agent,
        agent_config,
        manual_override=manual_override and effective_provider == "mock",
    )
    previous_status = org_agent.status if org_agent else None
    for attempt in range(1, spec.max_attempts + 1):
        if org_agent:
            org_agent.status = "running"
        run = AgentRun(
            agent_name=spec.name,
            task_type=spec.task_type,
            input_json={
                **_model_dump(agent_input),
                "attempt": attempt,
                "agent_spec": spec.metadata(),
                "agent_config_id": agent_config.id,
                "provider": effective_provider,
                "model": effective_model,
                "prompt_template_id": prompt_template.id if prompt_template else None,
                "prompt_version": prompt_template.version if prompt_template else None,
            },
            output_json={},
            status="running",
            provider=effective_provider,
            model=effective_model,
            prompt_template_id=prompt_template.id if prompt_template else None,
            prompt_version=prompt_template.version if prompt_template else None,
            started_at=now_utc(),
        )
        db.add(run)
        log_activity(
            db,
            actor_type="agent",
            actor_id=org_agent.id if org_agent else None,
            event_type="agent_run_started",
            entity_type="agent_run",
            entity_id=None,
            message=f"{spec.name} started {spec.task_type}.",
            metadata={"task_id": task.id if task else None, "attempt": attempt},
        )
        db.commit()
        db.refresh(run)

        try:
            result = handler()
            response: LLMResponse | None = None
            if isinstance(result, tuple):
                output, response = result
            else:
                output = result
            validated = spec.output_schema.model_validate(output)
            output_json = _model_dump(validated)
            status = output_json.get("status", "completed")
            if status not in TERMINAL_AGENT_STATES:
                raise PipelineError(f"{spec.name} returned non-terminal status: {status}")

            run.status = status
            run.output_json = output_json
            run.tokens_input = response.usage.tokens_input if response else int(output_json.get("tokens_input", 0))
            run.tokens_output = response.usage.tokens_output if response else int(output_json.get("tokens_output", 0))
            run.estimated_cost = response.usage.estimated_cost if response else float(output_json.get("estimated_cost", 0))
            if response:
                run.output_json = {**output_json, "_llm": {"provider": response.provider, "model": response.model}}
            run.finished_at = now_utc()
            relation = task.payload_json if task else {}
            create_cost_event_for_run(
                db,
                agent=org_agent,
                task_id=task.id if task else None,
                channel_id=relation.get("channel_id"),
                task_type=task.task_type if task else spec.task_type,
                provider=effective_provider,
                model=effective_model,
                tokens_input=run.tokens_input,
                tokens_output=run.tokens_output,
                estimated_cost=run.estimated_cost,
            )
            log_activity(
                db,
                actor_type="agent",
                actor_id=org_agent.id if org_agent else None,
                event_type="agent_run_completed",
                entity_type="agent_run",
                entity_id=run.id,
                message=f"{spec.name} completed {spec.task_type}.",
                metadata={"task_id": task.id if task else None, "status": status},
            )
            db.commit()

            if status in {"failed", "rejected"}:
                raise PipelineRejected(output_json.get("notes") or f"{spec.name} returned {status}")
            if org_agent and previous_status is not None:
                org_agent.status = previous_status if previous_status in {"paused", "idle"} else "idle"
                db.commit()
            return validated
        except Exception as exc:
            last_error = str(exc)
            if run.status == "running":
                run.status = "failed"
            run.error_message = last_error
            run.finished_at = now_utc()
            log_activity(
                db,
                actor_type="agent",
                actor_id=org_agent.id if org_agent else None,
                event_type="agent_run_failed",
                entity_type="agent_run",
                entity_id=run.id,
                message=f"{spec.name} failed {spec.task_type}: {last_error}",
                metadata={"task_id": task.id if task else None, "attempt": attempt},
            )
            if org_agent and previous_status is not None:
                org_agent.status = "failed" if previous_status != "paused" else previous_status
            db.commit()
            if attempt >= spec.max_attempts:
                raise PipelineError(last_error) from exc

    raise PipelineError(last_error or f"{spec.name} failed")


def _source_urls(topic: Topic) -> list[str]:
    urls: list[str] = []
    if topic.url:
        urls.append(topic.url)
    if topic.source and topic.source.url and topic.source.url not in urls:
        urls.append(topic.source.url)
    return urls


def _pipeline_agent_specs() -> list[AgentSpec]:
    return [RESEARCH_AGENT, FACTCHECK_AGENT, EDITOR_AGENT, CHIEF_EDITOR_AGENT]


def _ensure_real_dry_run_ready(db: Session, topic: Topic) -> None:
    if get_setting(db, "system_mode") != "dry_run":
        raise PipelineError("Real LLM dry-run is available only when system_mode=dry_run")
    if not _source_urls(topic):
        raise PipelineError("Topic must have at least one source URL for real LLM dry-run")
    not_ready: list[str] = []
    for spec in _pipeline_agent_specs():
        _agent, config, _prompt = get_agent_config(db, spec.name, manual_override=True)
        if config.provider == "mock":
            not_ready.append(f"{spec.name}: provider=mock")
        if not config.enabled:
            not_ready.append(f"{spec.name}: config disabled")
    if not_ready:
        raise PipelineError("Real LLM dry-run is not ready: " + "; ".join(not_ready))


def _post_generation_fields(
    *,
    generation_mode: str,
    provider_name: str,
    model_name: str,
    prompt_version: int | None,
    tokens_input: int,
    tokens_output: int,
    estimated_cost: float,
    structured_outputs: dict[str, Any],
) -> dict[str, Any]:
    if generation_mode == "mock":
        reason = "Mock content is not publishable"
    elif generation_mode == "dry_run":
        reason = "Dry-run content requires human review and cannot be publicly published"
    else:
        reason = ""
    return {
        "mock_only": generation_mode == "mock",
        "not_publishable_reason": reason,
        "generation_mode": generation_mode,
        "provider": provider_name,
        "model": model_name,
        "prompt_template_version": prompt_version,
        "publishable": False,
        "non_publishable_reason": reason,
        "tokens_input": tokens_input,
        "tokens_output": tokens_output,
        "estimated_cost_usd": estimated_cost,
        "structured_outputs_json": structured_outputs,
    }


def choose_channel(db: Session, topic: Topic, channel_id: int | None = None) -> Channel:
    if channel_id is not None:
        channel = db.get(Channel, channel_id)
        if channel is None:
            raise PipelineError("Channel not found")
        return channel

    if topic.source_id:
        mapped = db.execute(
            select(Channel)
            .join(SourceChannelMap, SourceChannelMap.channel_id == Channel.id)
            .where(SourceChannelMap.source_id == topic.source_id, SourceChannelMap.enabled.is_(True))
            .order_by(SourceChannelMap.relevance_weight.desc())
        ).scalars().first()
        if mapped:
            return mapped

    channel = db.execute(select(Channel).where(Channel.status == "active").order_by(Channel.id)).scalars().first()
    if channel is None:
        raise PipelineError("No active channels are configured")
    return channel


def _base_agent_input(topic: Topic, channel: Channel) -> dict[str, Any]:
    playbook = channel_playbook(channel.slug)
    return {
        "topic_id": topic.id,
        "channel_id": channel.id,
        "topic_title": topic.title,
        "channel_name": channel.name,
        "channel_category": channel.category,
        "channel_tone": channel.tone_of_voice,
        "forbidden_topics": channel.topics_forbidden or [],
        "source_urls": _source_urls(topic),
        "risk_threshold": channel.risk_threshold,
        "channel_playbook": playbook,
    }


def _score_alignment(channel: Channel, topic: Topic, body: str) -> bool:
    haystack = f"{topic.title} {topic.summary} {topic.raw_text} {body}".lower()
    category_terms = {
        "news": ["happened", "matters", "next", "event", "today", "update", "why"],
        "money": ["money", "business", "price", "cost", "income", "finance", "entrepreneur"],
        "ai": ["ai", "agent", "automation", "model", "tool", "workflow"],
        "health": ["health", "sleep", "nutrition", "habit", "energy", "study"],
        "food": ["food", "recipe", "meal", "cook", "budget", "ingredient"],
    }
    terms = category_terms.get(channel.category, [channel.category])
    return any(term in haystack for term in terms)


def _violates_forbidden(channel: Channel, topic: Topic, body: str) -> bool:
    haystack = f"{topic.title} {topic.summary} {topic.raw_text} {body}".lower()
    return any(term.lower() in haystack for term in channel.topics_forbidden or [])


def _adds_editorial_value(body: str) -> bool:
    text = body.lower()
    markers = [
        "why it matters",
        "practical",
        "checklist",
        "trend",
        "compare",
        "decision",
        "next step",
        "useful",
        "saves time",
        "matters",
    ]
    return any(marker in text for marker in markers)


def _risk_above_threshold(channel: Channel, risk_score: float) -> bool:
    threshold = float(channel.risk_threshold or 0.5)
    normalized = risk_score / 100 if risk_score > 1 else risk_score
    return normalized > threshold


def _contains_required_structure(draft: EditorOutput, playbook: dict[str, Any]) -> bool:
    body = draft.body.lower()
    required = [str(item) for item in playbook.get("required_structure", [])]
    if not required:
        return True
    used = {str(item).lower() for item in draft.required_structure_used}
    matched = 0
    for item in required:
        label = item.lower()
        marker = label.split("/")[0].strip()[:10]
        if label in used or marker in body:
            matched += 1
    return matched >= max(1, len(required) - 1)


def _decision_confidence(chief: ChiefEditorOutput) -> float:
    score = chief.overall_quality_score or chief.quality_score
    if score > 1:
        score = score / 100
    return round(max(0.0, min(1.0, float(score))), 3)


def _score_bundle(channel: Channel, topic: Topic, draft: EditorOutput, factcheck: FactcheckOutput) -> dict[str, float]:
    playbook = channel_playbook(channel.slug)
    unsupported = len(factcheck.unsupported_claims or [])
    risk_100 = factcheck.risk_score if factcheck.risk_score > 1 else factcheck.risk_score * 100
    editorial_value = 88 if _adds_editorial_value(draft.body) else 62
    factuality = max(40, 92 - unsupported * 18 - (15 if factcheck.decision in {"needs_human_review", "fail"} else 0))
    clarity = 86 if 120 <= len(draft.body) <= int(playbook.get("max_post_length", 1300)) else 68
    usefulness = 88 if draft.why_useful or "проверь" in draft.body.lower() or "попроб" in draft.body.lower() else 66
    channel_fit = 90 if _score_alignment(channel, topic, draft.body) and _contains_required_structure(draft, playbook) else 68
    originality = 82 if draft.editorial_value else 70
    overall = round((editorial_value * 0.2 + factuality * 0.22 + clarity * 0.14 + usefulness * 0.16 + channel_fit * 0.16 + originality * 0.12) - max(0, risk_100 - 50) * 0.1, 2)
    return {
        "editorial_value_score": float(editorial_value),
        "factuality_score": float(factuality),
        "clarity_score": float(clarity),
        "usefulness_score": float(usefulness),
        "channel_fit_score": float(channel_fit),
        "originality_score": float(originality),
        "risk_score": round(float(risk_100), 2),
        "overall_quality_score": max(0.0, min(100.0, overall)),
    }


def _quality_checks(channel: Channel, topic: Topic, draft: EditorOutput, factcheck: FactcheckOutput) -> dict[str, bool]:
    playbook = channel_playbook(channel.slug)
    return {
        "has_source_references": bool(draft.source_urls),
        "post_not_empty": bool(draft.title.strip() and draft.body.strip()),
        "adds_editorial_value": _adds_editorial_value(draft.body),
        "aligned_with_channel": _score_alignment(channel, topic, draft.body),
        "uses_channel_structure": _contains_required_structure(draft, playbook),
        "within_length_limit": len(draft.body) <= int(playbook.get("max_post_length", 1300)),
        "no_forbidden_topics": not _violates_forbidden(channel, topic, draft.body),
        "has_risk_score": factcheck.risk_score >= 0,
        "claims_supported": factcheck.supported_claims,
    }


def _quality_score(checks: dict[str, bool], factcheck: FactcheckOutput) -> float:
    passed = sum(1 for value in checks.values() if value)
    base = passed / max(len(checks), 1)
    risk = factcheck.risk_score / 100 if factcheck.risk_score > 1 else factcheck.risk_score
    penalty = min(0.25, risk * 0.2)
    return round(max(0.0, base - penalty), 3)


def _research_agent(topic: Topic, channel: Channel) -> ResearchOutput:
    source_urls = _source_urls(topic)
    happened = topic.summary or topic.raw_text[:500] or topic.title
    playbook = channel_playbook(channel.slug)
    return ResearchOutput(
        what_happened=happened,
        why_it_matters="This topic needs context, practical meaning, and a clear reason for the reader to care.",
        key_facts=[topic.title, happened[:240]],
        source_urls=source_urls,
        uncertainty="Mock research. Human review is required for sensitive or unsupported claims.",
        suggested_angles=[f"Use the {channel.name} formula: {' / '.join(playbook['editorial_formula'])}."],
        risk_notes="Mock research does not verify claims.",
    )


def _factcheck_agent(topic: Topic, channel: Channel, research: ResearchOutput) -> FactcheckOutput:
    text = f"{topic.title} {topic.summary} {topic.raw_text}".lower()
    risk_terms = [
        "diagnosis",
        "dosage",
        "treatment",
        "guaranteed income",
        "trading signal",
        "election",
        "war",
        "legal advice",
    ]
    risk_score = min(100.0, 12 + 16 * sum(term in text for term in risk_terms))
    if channel.category in {"health", "money", "news"}:
        risk_score = min(100.0, risk_score + 8)
    reliable_sources = bool(research.source_links)
    supported_claims = reliable_sources

    if not reliable_sources:
        return FactcheckOutput(
            status="rejected",
            factcheck_result="fail",
            result="fail",
            risk_score=risk_score,
            source_check="No source references were provided.",
            source_quality="missing",
            unsupported_claims=["No source references were provided."],
            reason="No source references were provided.",
            risk_notes="Cannot verify claims without sources.",
            human_review_required=True,
            requires_human_review=True,
        )

    if _risk_above_threshold(channel, risk_score):
        return FactcheckOutput(
            status="waiting_human",
            factcheck_result="needs_human_review",
            result="needs_human_review",
            risk_score=risk_score,
            source_check="Source references exist, but risk is above threshold.",
            source_quality="source-backed but requires cautious review",
            unsupported_claims=[] if supported_claims else ["Source support is incomplete."],
            reason="Risk score is above the channel threshold.",
            risk_notes="Human should verify sensitive claims, dates, and wording.",
            human_review_required=True,
            requires_human_review=True,
        )

    return FactcheckOutput(
        factcheck_result="pass",
        result="pass",
        risk_score=risk_score,
        source_check="Mock factcheck passed with source references.",
        source_quality="source-backed",
        unsupported_claims=[],
        reason="Mock factcheck passed with source references.",
        risk_notes="No high-risk unsupported claims detected in mock checks.",
        human_review_required=False,
        requires_human_review=False,
    )


def _editor_agent(
    topic: Topic,
    channel: Channel,
    research: ResearchOutput,
    factcheck: FactcheckOutput,
    provider: LLMProvider,
    rewrite_notes: list[str] | None = None,
) -> EditorOutput:
    notes = rewrite_notes or []
    playbook = channel_playbook(channel.slug)
    prompt = (
        f"Channel: {channel.name}\n"
        f"Category: {channel.category}\n"
        f"Tone: {channel.tone_of_voice}\n"
        f"Playbook:\n{playbook_summary(channel.slug)}\n"
        f"Topic: {topic.title}\n"
        f"Research: {research.model_dump_json()}\n"
        f"Factcheck: {factcheck.model_dump_json()}\n"
        f"Rewrite notes: {notes}\n"
        "Write a concise Russian MAX post using the channel required structure, source-aware wording, and no unsupported claims."
    )
    response = provider.generate(prompt, max_tokens=900)
    body = response.text
    if notes:
        body = (
            f"{body}\n\nUseful angle added: focus on why this matters, what to watch next, "
            "and one practical reader takeaway."
        )
    return EditorOutput(
        title=topic.title[:180],
        body=body,
        visual_prompt=f"Clean editorial visual for {channel.name}: {topic.title}",
        source_urls=research.source_links,
        editorial_value="Adds context, practical meaning and a clear reader takeaway.",
        why_useful=f"Useful for {playbook['audience']}",
        required_structure_used=playbook["required_structure"],
        channel_playbook_checklist={item: True for item in playbook["quality_checklist"][:4]},
        risk_notes=factcheck.notes,
        channel_fit_reason=f"Fits {channel.name} by focusing on {channel.category}.",
        tokens_input=response.usage.tokens_input,
        tokens_output=response.usage.tokens_output,
        estimated_cost=response.usage.estimated_cost,
    )


def _chief_editor_agent(
    topic: Topic,
    channel: Channel,
    draft: EditorOutput,
    factcheck: FactcheckOutput,
    rewrite_attempts_used: int,
) -> ChiefEditorOutput:
    checks = _quality_checks(channel, topic, draft, factcheck)
    issues = [name for name, passed in checks.items() if not passed]
    quality_score = _quality_score(checks, factcheck)
    scores = _score_bundle(channel, topic, draft, factcheck)
    playbook = channel_playbook(channel.slug)
    min_editorial_value = float(playbook.get("min_editorial_value_score", 70))
    human_checks = ["Verify source URLs and dates", "Check unsupported claims", "Confirm no public publishing before MAX step"]

    if factcheck.decision == "needs_human_review":
        return ChiefEditorOutput(
            status="waiting_human",
            decision="waiting_human",
            quality_score=quality_score,
            **scores,
            reason="Risk is above threshold.",
            required_changes=["risk_above_threshold", *issues],
            human_check_before_publication=human_checks,
            playbook_checklist=checks,
            publish_safety="dry_run_review_required",
            checks=checks,
        )

    if factcheck.decision == "fail":
        return ChiefEditorOutput(
            status="rejected",
            decision="reject",
            quality_score=quality_score,
            **scores,
            reason="Factcheck failed.",
            required_changes=["factcheck_failed", *issues],
            human_check_before_publication=human_checks,
            playbook_checklist=checks,
            publish_safety="dry_run_review_required",
            checks=checks,
        )

    if (
        rewrite_attempts_used == 0
        and (
            issues
            or scores["overall_quality_score"] < 70
            or scores["editorial_value_score"] < min_editorial_value
        )
    ):
        return ChiefEditorOutput(
            status="completed_with_warnings",
            decision="rewrite_once",
            quality_score=quality_score,
            **scores,
            reason="Quality checks require one controlled rewrite.",
            required_changes=issues or ["raise_editorial_value", "tighten_channel_structure"],
            human_check_before_publication=human_checks,
            playbook_checklist=checks,
            publish_safety="dry_run_review_required",
            checks=checks,
        )

    if scores["factuality_score"] < 75:
        return ChiefEditorOutput(
            status="waiting_human",
            decision="waiting_human",
            quality_score=quality_score,
            **scores,
            reason="Factuality score is below threshold.",
            required_changes=["verify_facts", *issues],
            human_check_before_publication=human_checks,
            playbook_checklist=checks,
            publish_safety="dry_run_review_required",
            checks=checks,
        )

    if _risk_above_threshold(channel, scores["risk_score"]):
        return ChiefEditorOutput(
            status="waiting_human",
            decision="waiting_human",
            quality_score=quality_score,
            **scores,
            reason="Risk score is above channel threshold.",
            required_changes=["human_risk_review", *issues],
            human_check_before_publication=human_checks,
            playbook_checklist=checks,
            publish_safety="dry_run_review_required",
            checks=checks,
        )

    if issues or scores["overall_quality_score"] < 70:
        return ChiefEditorOutput(
            status="rejected",
            decision="reject",
            quality_score=quality_score,
            **scores,
            reason="Quality score is too low after checks.",
            required_changes=issues or ["quality_score_too_low"],
            human_check_before_publication=human_checks,
            playbook_checklist=checks,
            publish_safety="dry_run_review_required",
            checks=checks,
        )

    return ChiefEditorOutput(
        decision="approve_for_review",
        quality_score=quality_score,
        **scores,
        reason="Post passed quality checks but still requires human review.",
        required_changes=[],
        human_check_before_publication=human_checks,
        playbook_checklist=checks,
        publish_safety="dry_run_review_required",
        checks=checks,
    )


def _create_task(db: Session, topic: Topic, channel: Channel) -> Task:
    idempotency_key = f"pipeline:{topic.id}:{channel.id}:v1"
    existing = db.execute(select(Task).where(Task.idempotency_key == idempotency_key)).scalar_one_or_none()
    if existing and existing.status == "completed":
        return existing
    task = existing or Task(
        task_type="run_topic_pipeline",
        payload_json={"topic_id": topic.id, "channel_id": channel.id},
        status="pending",
        attempts=0,
        max_attempts=1,
        idempotency_key=idempotency_key,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    log_activity(
        db,
        actor_type="system",
        actor_id=None,
        event_type="task_created",
        entity_type="task",
        entity_id=task.id,
        message=f"Task created: {task.task_type}",
        metadata=task.payload_json,
    )
    db.commit()
    return task


def _log_review_action(db: Session, *, post: Post, action: str, status: str, error_message: str | None = None) -> None:
    task = Task(
        task_type=f"review_{action}",
        payload_json={"post_id": post.id, "topic_id": post.topic_id, "channel_id": post.channel_id},
        status="completed" if error_message is None else "failed",
        attempts=1,
        max_attempts=1,
        completed_at=now_utc(),
        error_message=error_message,
        idempotency_key=f"review:{action}:{post.id}:{post.version}:{now_utc().timestamp()}",
    )
    run = AgentRun(
        agent_name="review_queue",
        task_type=action,
        input_json={"post_id": post.id, "topic_id": post.topic_id, "channel_id": post.channel_id},
        output_json={"status": status, "post_status": post.status},
        status=status,
        started_at=now_utc(),
        finished_at=now_utc(),
    )
    db.add_all([task, run])
    log_activity(
        db,
        actor_type="human",
        actor_id=None,
        event_type=f"post_{action}",
        entity_type="post",
        entity_id=post.id,
        message=f"Post #{post.id} review action: {action}.",
        metadata={"post_status": post.status, "topic_id": post.topic_id},
    )


def run_topic_pipeline(
    db: Session,
    *,
    topic_id: int,
    channel_id: int | None = None,
    llm_provider: LLMProvider | None = None,
    manual_override: bool = False,
    real_dry_run: bool = False,
) -> Post:
    topic = db.get(Topic, topic_id)
    if topic is None:
        raise PipelineError("Topic not found")
    if real_dry_run:
        manual_override = True
        _ensure_real_dry_run_ready(db, topic)
    channel = choose_channel(db, topic, channel_id)
    task = _create_task(db, topic, channel)

    existing_post_id = task.payload_json.get("post_id")
    if task.status == "completed" and existing_post_id:
        post = db.get(Post, existing_post_id)
        if post is not None:
            return post

    if task.attempts >= task.max_attempts:
        task.status = "failed"
        task.error_message = "Task max attempts exceeded"
        task.completed_at = now_utc()
        db.commit()
        raise PipelineError(task.error_message)

    issue = create_issue_for_pipeline(db, topic_id=topic.id, channel_id=channel.id)
    task.payload_json = {**task.payload_json, "issue_id": issue.id}
    db.commit()

    use_real_llm = real_dry_run and get_setting(db, "system_mode") == "dry_run"
    provider = llm_provider or provider_for_agent(db, EDITOR_AGENT.name, manual_override=manual_override)
    if not use_real_llm:
        provider = MockLLMProvider()
    llm_trace: dict[str, Any] = {"real_dry_run": use_real_llm, "runs": []}

    def call_llm(spec: AgentSpec, agent_input: BaseModel, fallback_system: str) -> tuple[BaseModel, LLMResponse]:
        output, response = _llm_structured_output(
            db,
            spec=spec,
            agent_input=agent_input,
            manual_override=manual_override,
            fallback_system=fallback_system,
        )
        llm_trace["runs"].append(
            {
                "agent": spec.name,
                "provider": response.provider,
                "model": response.model,
                "tokens_input": response.usage.tokens_input,
                "tokens_output": response.usage.tokens_output,
                "estimated_cost": response.usage.estimated_cost,
            }
        )
        return output, response
    task.status = "running"
    task.locked_at = now_utc()
    task.attempts += 1
    db.commit()

    try:
        base = _base_agent_input(topic, channel)

        topic.status = "researching"
        db.commit()
        research_input = ResearchInput(
            **base,
            topic_summary=topic.summary,
            topic_raw_text=topic.raw_text,
        )
        research = _run_agent(
            db,
            spec=RESEARCH_AGENT,
            agent_input=research_input,
            task=task,
            manual_override=manual_override,
            handler=lambda: call_llm(
                RESEARCH_AGENT,
                research_input,
                "You are a media research agent. Return verified, cautious research JSON for the topic.",
            )
            if use_real_llm
            else _research_agent(topic, channel),
        )
        assert isinstance(research, ResearchOutput)
        log_decision(
            db,
            issue_id=issue.id,
            entity_type="topic",
            entity_id=topic.id,
            decision="research_completed",
            reason=research.why_it_matters,
            confidence=0.72,
            alternatives=[{"decision": "send_to_human", "reason": research.uncertainty}],
        )

        topic.status = "researched"
        db.commit()

        factcheck_input = FactcheckInput(**base, research=research)
        factcheck = _run_agent(
            db,
            spec=FACTCHECK_AGENT,
            agent_input=factcheck_input,
            task=task,
            manual_override=manual_override,
            handler=lambda: call_llm(
                FACTCHECK_AGENT,
                factcheck_input,
                "You are a strict factcheck agent. Return JSON only and escalate unsupported or risky claims.",
            )
            if use_real_llm
            else _factcheck_agent(topic, channel, research),
        )
        assert isinstance(factcheck, FactcheckOutput)
        log_decision(
            db,
            issue_id=issue.id,
            entity_type="topic",
            entity_id=topic.id,
            decision=f"factcheck_{factcheck.decision}",
            reason=factcheck.notes,
            confidence=max(0.3, 1 - (factcheck.risk_score / 100 if factcheck.risk_score > 1 else factcheck.risk_score)),
            alternatives=[{"decision": "needs_human_review", "reason": "Escalate if risk threshold is exceeded"}],
        )

        if factcheck.decision == "fail":
            topic.status = "rejected"
            task.status = "failed"
            task.error_message = factcheck.notes
            task.completed_at = now_utc()
            db.commit()
            raise PipelineRejected(factcheck.notes)

        editor_input = EditorInput(**base, research=research, factcheck=factcheck)
        draft = _run_agent(
            db,
            spec=EDITOR_AGENT,
            agent_input=editor_input,
            task=task,
            manual_override=manual_override,
            handler=lambda: call_llm(
                EDITOR_AGENT,
                editor_input,
                "You are a Russian-language editor for MAX. Return a useful, source-aware post draft as JSON.",
            )
            if use_real_llm
            else _editor_agent(topic, channel, research, factcheck, provider),
        )
        assert isinstance(draft, EditorOutput)
        _agent, editor_config, editor_prompt = get_agent_config(db, EDITOR_AGENT.name, manual_override=manual_override)
        generation_mode = "dry_run" if use_real_llm else "mock"
        provider_name = editor_config.provider if use_real_llm else "mock"
        model_name = editor_config.model if use_real_llm else "mock"
        prompt_version = editor_prompt.version if editor_prompt else None
        tokens_input = sum(int(item.get("tokens_input", 0)) for item in llm_trace["runs"]) or draft.tokens_input
        tokens_output = sum(int(item.get("tokens_output", 0)) for item in llm_trace["runs"]) or draft.tokens_output
        estimated_cost = sum(float(item.get("estimated_cost", 0)) for item in llm_trace["runs"]) or draft.estimated_cost
        non_publishable_reason = (
            "Dry-run content requires human review and cannot be publicly published"
            if use_real_llm
            else "Mock content is not publishable"
        )
        structured_outputs = {
            "channel_playbook": channel_playbook(channel.slug),
            "research": _model_dump(research),
            "factcheck": _model_dump(factcheck),
            "editor": _model_dump(draft),
            "trace": llm_trace,
            "rewrite_history": [],
            "rewrite_attempts_used": 0,
        }

        post = Post(
            channel_id=channel.id,
            topic_id=topic.id,
            title=draft.title,
            body=draft.body,
            visual_prompt=draft.visual_prompt,
            source_urls=draft.source_urls,
            status="draft",
            risk_score=factcheck.risk_score,
            quality_score=0,
            created_by_agent=EDITOR_AGENT.name,
            generation_mode=generation_mode,
            provider=provider_name,
            model=model_name,
            prompt_template_version=prompt_version,
            publishable=False,
            non_publishable_reason=non_publishable_reason,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            estimated_cost_usd=estimated_cost,
            structured_outputs_json=structured_outputs,
            mock_only=(get_setting(db, "system_mode") == "mock" or getattr(provider, "provider_name", "") == "mock"),
            not_publishable_reason="MOCK / НЕ ДЛЯ ПУБЛИКАЦИИ: generated in mock mode." if (get_setting(db, "system_mode") == "mock" or getattr(provider, "provider_name", "") == "mock") else "",
        )
        db.add(post)
        db.commit()
        db.refresh(post)

        rewrite_attempts = 0
        chief_input = ChiefEditorInput(**base, post_id=post.id, draft=draft, factcheck=factcheck)
        chief = _run_agent(
            db,
            spec=CHIEF_EDITOR_AGENT,
            agent_input=chief_input,
            task=task,
            manual_override=manual_override,
            handler=lambda: call_llm(
                CHIEF_EDITOR_AGENT,
                chief_input,
                "You are the chief editor. Return a strict quality and publish-safety decision as JSON.",
            )
            if use_real_llm
            else _chief_editor_agent(topic, channel, draft, factcheck, rewrite_attempts),
        )
        assert isinstance(chief, ChiefEditorOutput)
        log_decision(
            db,
            issue_id=issue.id,
            entity_type="post",
            entity_id=post.id,
            decision=f"chief_editor_{chief.decision}",
            reason=", ".join(chief.issues) if chief.issues else "Post passed quality checks but still requires human review by MVP policy.",
            confidence=_decision_confidence(chief),
            alternatives=[{"decision": "rewrite_once", "reason": "Use exactly one rewrite if quality checks fail"}],
        )

        if chief.decision == "rewrite_once":
            rewrite_attempts = 1
            previous_version = {
                "version": post.version,
                "title": post.title,
                "body": post.body,
                "visual_prompt": post.visual_prompt,
                "source_urls": post.source_urls,
                "reason": "chief_editor_rewrite_once",
                "required_changes": chief.issues,
                "chief_editor": _model_dump(chief),
                "created_at": now_utc().isoformat(),
            }
            rewrite_input = EditorInput(
                **base,
                research=research,
                factcheck=factcheck,
                rewrite_notes=chief.issues,
            )
            draft = _run_agent(
                db,
                spec=REWRITE_AGENT,
                agent_input=rewrite_input,
                task=task,
                manual_override=manual_override,
                handler=lambda: call_llm(
                    REWRITE_AGENT,
                    rewrite_input,
                    "Rewrite the draft once according to the required changes. Return JSON only.",
                )
                if use_real_llm
                else _editor_agent(topic, channel, research, factcheck, provider, chief.issues),
            )
            assert isinstance(draft, EditorOutput)
            post.title = draft.title
            post.body = draft.body
            post.visual_prompt = draft.visual_prompt
            post.source_urls = draft.source_urls
            post.version += 1
            post.version_history = [*(post.version_history or []), previous_version]
            post.structured_outputs_json = {
                **(post.structured_outputs_json or {}),
                "editor_after_rewrite": _model_dump(draft),
                "rewrite_history": [
                    *((post.structured_outputs_json or {}).get("rewrite_history") or []),
                    {
                        "attempt": 1,
                        "required_changes": chief.issues,
                        "previous_version": previous_version["version"],
                        "new_version": post.version,
                    },
                ],
                "rewrite_attempts_used": rewrite_attempts,
            }
            db.commit()

            chief_input = ChiefEditorInput(
                **base,
                post_id=post.id,
                draft=draft,
                factcheck=factcheck,
                rewrite_attempts_used=rewrite_attempts,
            )
            chief = _run_agent(
                db,
                spec=CHIEF_EDITOR_AGENT,
                agent_input=chief_input,
                task=task,
                manual_override=manual_override,
                handler=lambda: call_llm(
                    CHIEF_EDITOR_AGENT,
                    chief_input,
                    "You are the chief editor. Return a strict quality and publish-safety decision as JSON.",
                )
                if use_real_llm
                else _chief_editor_agent(topic, channel, draft, factcheck, rewrite_attempts),
            )
            assert isinstance(chief, ChiefEditorOutput)
            log_decision(
                db,
                issue_id=issue.id,
                entity_type="post",
                entity_id=post.id,
                decision=f"chief_editor_after_rewrite_{chief.decision}",
                reason=chief.reason or (", ".join(chief.issues) if chief.issues else "Rewrite reviewed."),
                confidence=_decision_confidence(chief),
                alternatives=[{"decision": "waiting_human", "reason": "Escalate if one rewrite is not enough"}],
            )

        quality_scores = {
            "editorial_value_score": chief.editorial_value_score,
            "factuality_score": chief.factuality_score,
            "clarity_score": chief.clarity_score,
            "usefulness_score": chief.usefulness_score,
            "channel_fit_score": chief.channel_fit_score,
            "originality_score": chief.originality_score,
            "risk_score": chief.risk_score,
            "overall_quality_score": chief.overall_quality_score,
        }
        post.quality_score = chief.overall_quality_score or chief.quality_score
        post.risk_score = chief.risk_score or factcheck.risk_score
        post.risk_reason = factcheck.risk_notes or factcheck.notes
        post.quality_reason = chief.reason or (", ".join(chief.issues) if chief.issues else "Chief Editor checks passed")
        post.structured_outputs_json = {
            **(post.structured_outputs_json or {}),
            "channel_playbook": channel_playbook(channel.slug),
            "editor": _model_dump(draft),
            "chief_editor": _model_dump(chief),
            "quality_scores": quality_scores,
            "rewrite_attempts_used": rewrite_attempts,
            "trace": llm_trace,
        }
        post.tokens_input = sum(int(item.get("tokens_input", 0)) for item in llm_trace["runs"]) or post.tokens_input
        post.tokens_output = sum(int(item.get("tokens_output", 0)) for item in llm_trace["runs"]) or post.tokens_output
        post.estimated_cost_usd = sum(float(item.get("estimated_cost", 0)) for item in llm_trace["runs"]) or post.estimated_cost_usd

        if chief.decision in {"approve", "approve_for_review"}:
            require_review = bool(get_setting(db, "require_human_approval_for_all_posts"))
            post.status = "needs_review" if require_review else "approved"
            topic.status = "draft_ready"
            terminal_state = post.status
            post.status_reason = "Human approval required" if require_review else "Approved by policy"
            if post.status == "needs_review":
                create_notification(
                    db,
                    severity="info",
                    title="Пост ожидает проверки",
                    message=f"Пост #{post.id} готов к ручной проверке.",
                    entity_type="post",
                    entity_id=post.id,
                )
        elif chief.decision == "waiting_human":
            post.status = "needs_review"
            topic.status = "needs_human_review"
            terminal_state = "needs_review"
            post.status_reason = "Risk or quality gate requires human review"
            create_notification(
                db,
                severity="warning",
                title="Пост требует ручной проверки",
                message=f"Пост #{post.id} остановлен на risk/quality gate.",
                entity_type="post",
                entity_id=post.id,
            )
        else:
            post.status = "rejected"
            topic.status = "rejected"
            terminal_state = "rejected"
            post.status_reason = "Rejected by Chief Editor"

        task.status = "completed"
        task.completed_at = now_utc()
        task.payload_json = {
            **task.payload_json,
            "post_id": post.id,
            "terminal_state": terminal_state,
            "rewrite_attempts_used": rewrite_attempts,
        }
        log_activity(
            db,
            actor_type="system",
            actor_id=None,
            event_type="task_completed",
            entity_type="task",
            entity_id=task.id,
            message=f"Task completed: {task.task_type}",
            metadata=task.payload_json,
        )
        update_issue(
            db,
            issue,
            status="review" if post.status == "needs_review" else ("completed" if post.status == "approved" else "failed"),
            result_summary=f"Pipeline finished with post status {post.status}",
            post_id=post.id,
        )
        db.commit()
        db.refresh(post)
        return post
    except Exception as exc:
        is_budget_error = "budget" in str(exc).lower() or "token limit" in str(exc).lower()
        if is_budget_error:
            topic.status = "needs_human_review"
            task.status = "waiting_human"
        elif topic.status not in {"rejected", "needs_human_review"}:
            topic.status = "rejected"
            task.status = "failed"
        task.error_message = str(exc)
        task.completed_at = now_utc()
        log_activity(
            db,
            actor_type="system",
            actor_id=None,
            event_type="budget_limit_reached" if is_budget_error else "task_failed",
            entity_type="task",
            entity_id=task.id,
            message=f"Task failed: {task.task_type}: {exc}",
            metadata=task.payload_json,
        )
        update_issue(db, issue, status="failed", result_summary=str(exc), post_id=None)
        if not is_budget_error:
            create_notification(
                db,
                severity="critical",
                title="Pipeline завершился ошибкой",
                message=str(exc),
                entity_type="topic",
                entity_id=topic.id,
            )
        db.commit()
        raise


def generate_draft_for_topic(
    db: Session,
    *,
    topic_id: int,
    channel_id: int | None = None,
    llm_provider: LLMProvider | None = None,
) -> Post:
    return run_topic_pipeline(db, topic_id=topic_id, channel_id=channel_id, llm_provider=llm_provider, manual_override=True)


def run_real_dry_run_pipeline(
    db: Session,
    *,
    topic_id: int,
    channel_id: int | None = None,
) -> Post:
    return run_topic_pipeline(
        db,
        topic_id=topic_id,
        channel_id=channel_id,
        manual_override=True,
        real_dry_run=True,
    )


def approve_post(db: Session, post_id: int, approved_by: str = "human") -> Post:
    post = db.get(Post, post_id)
    if post is None:
        raise PipelineError("Post not found")
    if post.status == "rejected":
        raise PipelineError("Rejected posts cannot be approved without rewrite")
    if post.mock_only or not post.publishable:
        raise PipelineError(post.non_publishable_reason or post.not_publishable_reason or "Post is not publishable")
    post.status = "approved"
    post.approved_by = approved_by
    _log_review_action(db, post=post, action="approve_post", status="completed")
    db.commit()
    db.refresh(post)
    return post


def reject_post(db: Session, post_id: int) -> Post:
    post = db.get(Post, post_id)
    if post is None:
        raise PipelineError("Post not found")
    post.status = "rejected"
    if post.topic:
        post.topic.status = "rejected"
    _log_review_action(db, post=post, action="reject_post", status="rejected")
    db.commit()
    db.refresh(post)
    return post


def schedule_post(db: Session, post_id: int, scheduled_at: datetime | None = None) -> Post:
    post = db.get(Post, post_id)
    if post is None:
        raise PipelineError("Post not found")
    if post.status not in {"approved", "scheduled"}:
        raise PipelineError("Only approved or scheduled posts can be scheduled")
    if post.mock_only or not post.publishable:
        raise PipelineError(post.non_publishable_reason or post.not_publishable_reason or "Post is not publishable")
    post.status = "scheduled"
    post.scheduled_at = scheduled_at or now_utc() + timedelta(hours=1)
    _log_review_action(db, post=post, action="schedule_post", status="scheduled")
    db.commit()
    db.refresh(post)
    return post


def request_post_rewrite(
    db: Session,
    post_id: int,
    *,
    notes: list[str] | None = None,
    llm_provider: LLMProvider | None = None,
) -> Post:
    post = db.get(Post, post_id)
    if post is None:
        raise PipelineError("Post not found")
    if post.topic is None:
        raise PipelineError("Post has no topic")
    if post.version >= 2:
        raise PipelineError("Rewrite limit reached for this MVP post")

    topic = post.topic
    channel = post.channel
    provider = llm_provider or provider_for_agent(db, REWRITE_AGENT.name, manual_override=True)
    base = _base_agent_input(topic, channel)
    research = ResearchOutput(
        what_happened=topic.summary or topic.raw_text[:500] or topic.title,
        why_it_matters="Rewrite requested by human reviewer.",
        key_facts=[topic.title],
        source_urls=post.source_urls,
        uncertainty="Rewrite uses existing draft context.",
        suggested_angles=["Make the post more useful and clearer without adding unsupported claims."],
        risk_notes="Rewrite uses previous review context.",
    )
    factcheck = FactcheckOutput(
        result="pass_with_caution" if post.risk_score else "pass",
        risk_score=post.risk_score,
        source_check="Rewrite keeps previous source context.",
        unsupported_claims=[] if post.source_urls else ["No source references on the existing post."],
        reason="Rewrite keeps previous risk score.",
        requires_human_review=False,
    )
    rewrite_input = EditorInput(
        **base,
        research=research,
        factcheck=factcheck,
        rewrite_notes=notes or ["make_more_useful"],
    )
    draft = _run_agent(
        db,
        spec=REWRITE_AGENT,
        agent_input=rewrite_input,
        task=None,
        manual_override=True,
        handler=lambda: _editor_agent(topic, channel, research, factcheck, provider, notes or ["make_more_useful"]),
    )
    assert isinstance(draft, EditorOutput)

    post.title = draft.title
    post.body = draft.body
    post.visual_prompt = draft.visual_prompt
    post.source_urls = draft.source_urls
    history = list(post.version_history or [])
    history.append(
        {
            "version": post.version,
            "title": post.title,
            "body": post.body,
            "changed_at": now_utc().isoformat(),
            "reason": "rewrite_requested",
        }
    )
    post.version_history = history
    post.version += 1
    post.status = "needs_review"
    post.status_reason = "Rewrite requested by human reviewer"
    _log_review_action(db, post=post, action="request_rewrite", status="completed")
    db.commit()
    db.refresh(post)
    return post
