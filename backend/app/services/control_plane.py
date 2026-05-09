from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.all_models import DecisionLog, Issue, OrgAgent
from app.services.org import find_org_agent, log_activity


def find_agent_by_name(db: Session, name: str) -> OrgAgent | None:
    return db.execute(select(OrgAgent).where(OrgAgent.name == name)).scalar_one_or_none()


def create_issue_for_pipeline(db: Session, *, topic_id: int, channel_id: int | None) -> Issue:
    owner = find_agent_by_name(db, "ai_editor_agent") or find_org_agent(db, "editor_agent")
    reviewer = find_agent_by_name(db, "editor_in_chief")
    issue = Issue(
        title=f"Создать черновик для темы #{topic_id}",
        description="Pipeline: research -> factcheck -> editor -> chief editor -> review queue.",
        issue_type="draft",
        owner_agent_id=owner.id if owner else None,
        reviewer_agent_id=reviewer.id if reviewer else None,
        related_channel_id=channel_id,
        related_topic_id=topic_id,
        priority="normal",
        status="in_progress",
        next_action="Run safe topic pipeline and send resulting post to review.",
        target_metric="draft_candidates",
        target_value=1,
        current_value=0,
        progress_json={"pipeline": "research_factcheck_editor_chief_editor"},
    )
    db.add(issue)
    db.flush()
    issue.root_issue_id = issue.id
    log_activity(
        db,
        actor_type="system",
        actor_id=None,
        event_type="issue_created",
        entity_type="issue",
        entity_id=issue.id,
        message=f"Issue created: {issue.title}",
        metadata={"topic_id": topic_id, "channel_id": channel_id},
    )
    return issue


def update_issue(
    db: Session,
    issue: Issue | None,
    *,
    status: str,
    result_summary: str,
    post_id: int | None = None,
) -> None:
    if issue is None:
        return
    previous_status = issue.status
    issue.status = status
    issue.result_summary = result_summary
    if post_id is not None:
        issue.related_post_id = post_id
    if status in {"completed", "failed", "cancelled"}:
        issue.completed_at = datetime.now(UTC)
    if status == "review":
        issue.next_action = "Supervisor should review pipeline output."
    elif status == "completed":
        issue.next_action = "No further action."
        issue.current_value = issue.target_value or issue.current_value
    elif status == "failed":
        issue.blocked_reason = result_summary
        issue.next_action = "Human or supervisor must decide whether to retry or cancel."
    log_activity(
        db,
        actor_type="system",
        actor_id=None,
        event_type="issue_updated",
        entity_type="issue",
        entity_id=issue.id,
        message=f"Issue #{issue.id}: {status}",
        metadata={"post_id": post_id, "result_summary": result_summary},
    )
    if previous_status != status:
        db.add(
            DecisionLog(
                issue_id=issue.id,
                entity_type="issue",
                entity_id=issue.id,
                decision=f"move_{previous_status}_to_{status}",
                reason=result_summary,
                confidence=0.8,
                alternatives_json=[{"source": "pipeline"}],
            )
        )


def log_decision(
    db: Session,
    *,
    entity_type: str,
    entity_id: int | None,
    decision: str,
    reason: str,
    confidence: float,
    issue_id: int | None = None,
    agent_run_id: int | None = None,
    alternatives: list[dict[str, Any]] | None = None,
) -> DecisionLog:
    item = DecisionLog(
        agent_run_id=agent_run_id,
        issue_id=issue_id,
        entity_type=entity_type,
        entity_id=entity_id,
        decision=decision,
        reason=reason,
        confidence=confidence,
        alternatives_json=alternatives or [],
    )
    db.add(item)
    db.flush()
    log_activity(
        db,
        actor_type="agent",
        actor_id=None,
        event_type="decision_logged",
        entity_type=entity_type,
        entity_id=entity_id,
        message=f"Decision logged: {decision}",
        metadata={"issue_id": issue_id, "confidence": confidence},
    )
    return item
