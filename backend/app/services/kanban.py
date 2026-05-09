from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.all_models import DecisionLog, Issue
from app.services.org import log_activity

ISSUE_STATUSES = {"backlog", "ready", "in_progress", "review", "waiting_human", "completed", "failed", "cancelled"}
TERMINAL_ISSUE_STATUSES = {"completed", "failed", "cancelled"}
ISSUE_TRANSITIONS = {
    "backlog": {"ready", "cancelled"},
    "ready": {"in_progress", "cancelled"},
    "in_progress": {"review", "waiting_human", "failed", "cancelled"},
    "review": {"waiting_human", "completed", "failed", "cancelled"},
    "waiting_human": {"in_progress", "completed", "cancelled"},
    "completed": set(),
    "failed": set(),
    "cancelled": set(),
}
CHILD_TERMINAL_STATUSES = {"completed", "cancelled", "failed"}


def allowed_transitions(status: str) -> list[str]:
    return sorted(ISSUE_TRANSITIONS.get(status, set()))


class KanbanStateMachine:
    def __init__(self, db: Session) -> None:
        self.db = db

    def validate_transition(self, issue: Issue, target_status: str) -> None:
        if target_status not in ISSUE_STATUSES:
            self._log_rejection(issue, target_status, f"Unknown issue status: {target_status}")
            raise ValueError(f"Unknown issue status: {target_status}")
        if target_status == issue.status:
            return
        allowed = ISSUE_TRANSITIONS.get(issue.status, set())
        if target_status not in allowed:
            self._log_rejection(issue, target_status, f"Illegal issue status move: {issue.status} -> {target_status}")
            raise ValueError(f"Illegal issue status move: {issue.status} -> {target_status}")
        if target_status == "completed":
            blockers = self.parent_completion_blockers(issue)
            if blockers:
                reason = "Parent issue cannot complete until sub-issues are terminal with explanations"
                self._log_rejection(issue, target_status, reason, {"blockers": blockers})
                raise ValueError(reason)

    def parent_completion_blockers(self, issue: Issue) -> list[dict[str, Any]]:
        children = self.db.execute(select(Issue).where(Issue.parent_issue_id == issue.id)).scalars().all()
        blockers: list[dict[str, Any]] = []
        for child in children:
            terminal_without_summary = child.status in CHILD_TERMINAL_STATUSES and not (child.result_summary or "").strip()
            if child.status not in CHILD_TERMINAL_STATUSES or terminal_without_summary:
                blockers.append({"id": child.id, "title": child.title, "status": child.status})
        return blockers

    def transition(
        self,
        issue: Issue,
        target_status: str,
        *,
        actor_type: str,
        actor_id: int | None,
        reason: str,
        create_decision: bool = False,
        confidence: float = 0.82,
    ) -> bool:
        self.validate_transition(issue, target_status)
        if target_status == issue.status:
            return False
        previous = issue.status
        issue.status = target_status
        if target_status in TERMINAL_ISSUE_STATUSES and issue.completed_at is None:
            issue.completed_at = datetime.now(UTC)
        log_activity(
            self.db,
            actor_type=actor_type,
            actor_id=actor_id,
            event_type="issue_transitioned",
            entity_type="issue",
            entity_id=issue.id,
            message=f"Issue #{issue.id}: {previous} -> {target_status}",
            metadata={"from": previous, "to": target_status, "reason": reason},
        )
        if create_decision:
            self.db.add(
                DecisionLog(
                    issue_id=issue.id,
                    entity_type="issue",
                    entity_id=issue.id,
                    decision=f"move_{previous}_to_{target_status}",
                    reason=reason,
                    confidence=confidence,
                    alternatives_json=[{"allowed_next": allowed_transitions(target_status)}],
                )
            )
        return True

    def _log_rejection(self, issue: Issue, target_status: str, reason: str, metadata: dict[str, Any] | None = None) -> None:
        log_activity(
            self.db,
            actor_type="system",
            actor_id=None,
            event_type="issue_transition_rejected",
            entity_type="issue",
            entity_id=issue.id,
            message=f"Issue transition rejected: {issue.status} -> {target_status}. {reason}",
            metadata={"from": issue.status, "to": target_status, **(metadata or {})},
        )


def issue_tree_progress(db: Session, issue: Issue) -> dict[str, Any]:
    children = db.execute(select(Issue).where(Issue.parent_issue_id == issue.id)).scalars().all()
    total = len(children)
    completed = len([child for child in children if child.status == "completed"])
    terminal = len([child for child in children if child.status in CHILD_TERMINAL_STATUSES])
    failed = len([child for child in children if child.status == "failed"])
    return {
        "sub_issues_total": total,
        "sub_issues_completed": completed,
        "sub_issues_terminal": terminal,
        "sub_issues_failed": failed,
        "percent": round((terminal / total) * 100, 1) if total else 0,
    }


def count_children(db: Session, issue_id: int) -> int:
    return int(db.scalar(select(func.count()).select_from(Issue).where(Issue.parent_issue_id == issue_id)) or 0)
