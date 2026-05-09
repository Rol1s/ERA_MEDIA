from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, time
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.all_models import Channel, DecisionLog, Issue, OperatingLoopRun, OrgAgent, Post, Topic
from app.services.kanban import KanbanStateMachine, allowed_transitions, issue_tree_progress
from app.services.notifications import create_notification
from app.services.org import daily_agent_usage, log_activity
from app.services.settings import daily_global_usage, get_settings

MAX_CREATED_ISSUES_PER_RUN = 20
MAX_UPDATED_ISSUES_PER_RUN = 50
MAX_ITERATIONS_PER_RUN = 1
MAX_RUNTIME_SECONDS = 60

DAILY_CHANNEL_TARGETS = [
    ("era-now", "ERA Сейчас draft candidates", "news_editor_agent", 8),
    ("era-money", "ERA Деньги draft candidates", "money_editor_agent", 4),
    ("era-ai", "ERA AI draft candidates", "ai_editor_agent", 5),
    ("era-health", "ERA Здоровье draft candidates", "health_editor_agent", 3),
    ("era-food", "ERA Еда draft candidates", "food_editor_agent", 4),
]


@dataclass
class LoopCounters:
    issues_created: int = 0
    issues_updated: int = 0
    issues_moved: int = 0
    decisions_made: int = 0
    warnings: list[dict[str, Any]] = field(default_factory=list)
    created_issue_ids: list[int] = field(default_factory=list)
    updated_issue_ids: list[int] = field(default_factory=list)
    moved_issue_ids: list[int] = field(default_factory=list)
    human_input_issue_ids: list[int] = field(default_factory=list)


class IssueAssignmentService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def agent(self, name: str) -> OrgAgent | None:
        return self.db.execute(select(OrgAgent).where(OrgAgent.name == name)).scalar_one_or_none()

    def assign(self, issue_type: str, *, channel: Channel | None = None) -> tuple[OrgAgent | None, OrgAgent | None]:
        channel_editor = {
            "era-now": "news_editor_agent",
            "era-money": "money_editor_agent",
            "era-ai": "ai_editor_agent",
            "era-health": "health_editor_agent",
            "era-food": "food_editor_agent",
        }.get(channel.slug if channel else "")
        if issue_type == "discovery":
            return self.agent("intelligence_director"), self.agent("media_director")
        if issue_type in {"world_scout", "source_health"}:
            return self.agent("world_scout_agent"), self.agent("intelligence_director")
        if issue_type in {"draft", "channel_draft"}:
            return self.agent(channel_editor or "editor_in_chief"), self.agent("editor_in_chief")
        if issue_type == "factcheck":
            return self.agent("factcheck_agent"), self.agent("quality_director")
        if issue_type == "risk":
            return self.agent("risk_control_agent"), self.agent("quality_director")
        if issue_type == "review":
            return self.agent("editor_in_chief"), self.agent("human_owner")
        if issue_type == "visual":
            return self.agent("visual_agent"), self.agent("creative_director")
        if issue_type == "analytics":
            return self.agent("analytics_agent"), self.agent("growth_director")
        if issue_type == "publish":
            publisher = self.agent("publisher_agent")
            if publisher and publisher.status != "disabled":
                return publisher, self.agent("human_owner")
            return None, self.agent("human_owner")
        return self.agent("media_director"), self.agent("human_owner")


class SupervisorReviewService:
    def __init__(self, db: Session) -> None:
        self.assignments = IssueAssignmentService(db)

    def reviewer_for(self, issue_type: str, *, channel: Channel | None = None, high_risk: bool = False) -> OrgAgent | None:
        if high_risk:
            return self.assignments.agent("human_owner")
        return self.assignments.assign(issue_type, channel=channel)[1]


class AgentOperatingLoop:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.assignments = IssueAssignmentService(db)
        self.reviewers = SupervisorReviewService(db)
        self.kanban = KanbanStateMachine(db)
        self.counters = LoopCounters()
        self.settings = get_settings(db)
        self.today = datetime.now(UTC).date().isoformat()
        self.started_at = datetime.now(UTC)
        self.media_director = self.assignments.agent("media_director")

    def run(self, *, action: str, mode: str = "manual_run") -> OperatingLoopRun:
        if action not in {"create_daily_plan", "refresh_kanban", "check_blockers"}:
            raise ValueError(f"Unknown operating loop action: {action}")
        if mode not in {"manual_run", "dry_run", "scheduled"}:
            raise ValueError(f"Unknown operating loop mode: {mode}")

        planning_only = bool(not self.settings.get("global_agents_enabled") or mode == "dry_run")
        run = OperatingLoopRun(mode=mode, action=action, planning_only=planning_only, status="running")
        self.db.add(run)
        self.db.flush()

        try:
            self._preflight(planning_only=planning_only)
            if action == "create_daily_plan":
                self._create_daily_plan()
                self._refresh_kanban()
                self._check_blockers()
            elif action == "refresh_kanban":
                self._refresh_kanban()
            elif action == "check_blockers":
                self._check_blockers()
            report = self._build_report(action=action, mode=mode, planning_only=planning_only)
            run.status = "completed_with_warnings" if self.counters.warnings else "completed"
            run.report_json = report
        except Exception as exc:
            run.status = "failed"
            run.error_message = str(exc)
            self.counters.warnings.append({"type": "operating_loop_failed", "message": str(exc)})
            run.report_json = self._build_report(action=action, mode=mode, planning_only=planning_only)
        finally:
            run.issues_created = self.counters.issues_created
            run.issues_updated = self.counters.issues_updated
            run.issues_moved = self.counters.issues_moved
            run.decisions_made = self.counters.decisions_made
            run.warnings_json = self.counters.warnings
            run.finished_at = datetime.now(UTC)
            log_activity(
                self.db,
                actor_type="agent",
                actor_id=self.media_director.id if self.media_director else None,
                event_type="operating_loop_completed" if run.status != "failed" else "operating_loop_failed",
                entity_type="operating_loop_run",
                entity_id=run.id,
                message=f"CEO loop {action} finished with status {run.status}.",
                metadata=run.report_json,
            )
            self.db.commit()
            self.db.refresh(run)
        return run

    def _preflight(self, *, planning_only: bool) -> None:
        if self.media_director is None:
            raise RuntimeError("Media Director Agent is missing")
        if self.media_director.status == "disabled":
            raise RuntimeError("Media Director Agent is disabled")
        usage = daily_global_usage(self.db)
        if float(usage["cost"]) >= float(self.settings["global_daily_budget_usd"]):
            raise RuntimeError("Global daily budget exceeded")
        if int(usage["tokens"]) >= int(self.settings["global_daily_token_limit"]):
            raise RuntimeError("Global daily token limit exceeded")
        if planning_only:
            self.counters.warnings.append(
                {
                    "type": "planning_only",
                    "message": "Global agents are disabled or dry_run mode is active: CEO loop will only plan Kanban work.",
                }
            )

    def _create_daily_plan(self) -> None:
        parent = self._upsert_issue(
            key=f"daily_content_plan:{self.today}",
            title=f"Daily Content Plan {self.today}",
            description="CEO operating plan for ERA Media Factory.",
            issue_type="planning",
            owner_name="media_director",
            reviewer_name="human_owner",
            target_metric="daily_content_plan",
            target_value=1,
            current_value=0,
            next_action="Coordinate directors and track all required daily sub-issues.",
            progress={"target_label": "Daily plan with discovery, drafts, factcheck, review and analytics"},
        )
        parent.root_issue_id = parent.id

        discovery = self._upsert_issue(
            key=f"daily_content_plan:{self.today}:discovery",
            title="Discovery Run",
            description="Find candidate topics and check source coverage.",
            issue_type="discovery",
            owner_name="intelligence_director",
            reviewer_name="media_director",
            parent=parent,
            target_metric="candidate_topics",
            target_value=100,
            current_value=self._topics_today(),
            next_action="Prepare World Scout topic collection and source health work.",
            progress={"target_label": "Find 100 candidate topics"},
        )
        self._upsert_issue(
            key=f"daily_content_plan:{self.today}:world_scout",
            title="World Scout topic collection",
            description="Collect and normalize candidate topics. Do not draft posts directly.",
            issue_type="world_scout",
            owner_name="world_scout_agent",
            reviewer_name="intelligence_director",
            parent=discovery,
            target_metric="candidate_topics",
            target_value=100,
            current_value=self._topics_today(),
            next_action="Run World Scout only when content-agent execution is explicitly enabled.",
            progress={"planning_only_safe": True},
        )
        self._upsert_issue(
            key=f"daily_content_plan:{self.today}:source_health",
            title="Source health check",
            description="Check source availability, trust and channel assignments.",
            issue_type="source_health",
            owner_name="world_scout_agent",
            reviewer_name="intelligence_director",
            parent=discovery,
            target_metric="source_health_checks",
            target_value=1,
            current_value=0,
            next_action="Review source health before autonomous collection is enabled.",
            progress={"planning_only_safe": True},
        )

        draft_batch = self._upsert_issue(
            key=f"daily_content_plan:{self.today}:draft_batch",
            title="Channel Draft Batch",
            description="Prepare draft candidate capacity for all five channels.",
            issue_type="draft",
            owner_name="editor_in_chief",
            reviewer_name="media_director",
            parent=parent,
            target_metric="draft_candidates",
            target_value=sum(target for *_rest, target in DAILY_CHANNEL_TARGETS),
            current_value=self._posts_today(),
            next_action="Delegate channel draft tasks to channel editors.",
            progress={"target_label": "24 draft candidates across five channels"},
        )
        channels_by_slug = {channel.slug: channel for channel in self.db.execute(select(Channel)).scalars()}
        for slug, title, owner_name, target in DAILY_CHANNEL_TARGETS:
            channel = channels_by_slug.get(slug)
            self._upsert_issue(
                key=f"daily_content_plan:{self.today}:draft:{slug}",
                title=title,
                description=f"Prepare {target} useful draft candidates for {channel.name if channel else slug}.",
                issue_type="channel_draft",
                owner_name=owner_name,
                reviewer_name="editor_in_chief",
                parent=draft_batch,
                channel=channel,
                target_metric="draft_candidates",
                target_value=target,
                current_value=self._posts_today(channel),
                next_action="Select approved topics, run draft pipeline only when agents are enabled, then send to review.",
                progress={"channel_slug": slug, "mock_content_not_publishable": True},
            )

        factcheck_batch = self._upsert_issue(
            key=f"daily_content_plan:{self.today}:factcheck_batch",
            title="Factcheck Batch",
            description="Check all risky or high-impact topics/posts.",
            issue_type="factcheck",
            owner_name="quality_director",
            reviewer_name="editor_in_chief",
            parent=parent,
            target_metric="risky_items_checked",
            target_value=self._risky_items_count(),
            current_value=0,
            next_action="Run factcheck and risk review for risky/high-impact items.",
            progress={"target_label": "All risky/high-impact items"},
        )
        self._upsert_issue(
            key=f"daily_content_plan:{self.today}:factcheck_posts",
            title="Factcheck post batch",
            description="Verify sources, dates and supported claims.",
            issue_type="factcheck",
            owner_name="factcheck_agent",
            reviewer_name="quality_director",
            parent=factcheck_batch,
            target_metric="risky_items_checked",
            target_value=self._risky_items_count(),
            current_value=0,
            next_action="Check source validity before posts can move forward.",
            progress={"risk_gate": "factcheck"},
        )
        self._upsert_issue(
            key=f"daily_content_plan:{self.today}:risk_review",
            title="Risk review post batch",
            description="Review health, finance, legal, political and reputational risk.",
            issue_type="risk",
            owner_name="risk_control_agent",
            reviewer_name="quality_director",
            parent=factcheck_batch,
            target_metric="risk_reviews",
            target_value=self._risky_items_count(),
            current_value=0,
            next_action="Escalate high-risk posts to Human Owner.",
            progress={"risk_gate": "risk_control"},
        )

        self._upsert_issue(
            key=f"daily_content_plan:{self.today}:human_review",
            title="Human Review Batch",
            description="Process all posts currently waiting for review.",
            issue_type="review",
            owner_name="editor_in_chief",
            reviewer_name="human_owner",
            parent=parent,
            target_metric="needs_review_processed",
            target_value=self._needs_review_count(),
            current_value=0,
            next_action="Human/editorial review must approve, edit, reject or archive waiting posts.",
            progress={"remaining_needs_review": self._needs_review_count()},
            required_human_action="Review needs_review posts before any publication step exists.",
        )
        self._upsert_issue(
            key=f"daily_content_plan:{self.today}:analytics",
            title="Analytics Report",
            description="Prepare daily performance report and recommendations.",
            issue_type="analytics",
            owner_name="analytics_agent",
            reviewer_name="growth_director",
            parent=parent,
            target_metric="daily_report",
            target_value=1,
            current_value=0,
            next_action="Prepare performance summary after metrics are available.",
            progress={"target_label": "Daily performance report"},
        )
        self._update_parent_progress(parent)

    def _refresh_kanban(self) -> None:
        issues = self.db.execute(select(Issue).where(Issue.status.notin_(["completed", "failed", "cancelled"])).limit(200)).scalars().all()
        for issue in issues:
            if self.counters.issues_updated >= MAX_UPDATED_ISSUES_PER_RUN:
                self.counters.warnings.append({"type": "updated_issue_limit", "message": "Max updated issues per run reached."})
                break
            self._refresh_issue_progress(issue)
            self._apply_assignment_blockers(issue)
            self.counters.issues_updated += 1
            self.counters.updated_issue_ids.append(issue.id)
            if issue.status == "backlog" and issue.owner_agent_id and issue.reviewer_agent_id and not issue.blocked_reason:
                self._move(issue, "ready", "Issue has owner/reviewer and is ready for supervised work.")
            if issue.status == "in_progress" and issue.target_value > 0 and issue.current_value >= issue.target_value:
                self._move(issue, "review", "Issue target has been reached and requires supervisor review.")
            if self._runtime_exceeded():
                self.counters.warnings.append({"type": "runtime_limit", "message": "CEO loop stopped before processing all issues."})
                break

    def _check_blockers(self) -> None:
        issues = self.db.execute(select(Issue).where(Issue.status.notin_(["completed", "failed", "cancelled"])).limit(200)).scalars().all()
        for issue in issues:
            if self.counters.issues_updated >= MAX_UPDATED_ISSUES_PER_RUN:
                self.counters.warnings.append({"type": "updated_issue_limit", "message": "Max updated issues per run reached."})
                break
            self._apply_assignment_blockers(issue)
            self.counters.issues_updated += 1
            self.counters.updated_issue_ids.append(issue.id)
            failed_children = self.db.execute(select(Issue).where(Issue.parent_issue_id == issue.id, Issue.status == "failed")).scalars().all()
            if failed_children:
                issue.blocked_reason = "One or more required sub-issues failed."
                issue.required_human_action = "Review failed sub-issues and decide whether to retry, cancel or accept the failure."
                issue.next_action = "Human Owner or reviewer must resolve failed sub-issues."
                self._move_to_waiting_human(issue, "Failed sub-issue requires human decision.")
                self.counters.human_input_issue_ids.append(issue.id)
                create_notification(
                    self.db,
                    severity="warning",
                    title="Задача требует решения человека",
                    message=f"Issue #{issue.id} blocked by failed sub-issue.",
                    entity_type="issue",
                    entity_id=issue.id,
                )
            if issue.status == "waiting_human":
                self.counters.human_input_issue_ids.append(issue.id)
                if not issue.required_human_action:
                    issue.required_human_action = "Review this issue and choose the next valid transition."
            if self._runtime_exceeded():
                self.counters.warnings.append({"type": "runtime_limit", "message": "CEO loop stopped before checking all blockers."})
                break

    def _upsert_issue(
        self,
        *,
        key: str,
        title: str,
        description: str,
        issue_type: str,
        owner_name: str,
        reviewer_name: str,
        target_metric: str,
        target_value: float,
        current_value: float,
        next_action: str,
        progress: dict[str, Any],
        parent: Issue | None = None,
        channel: Channel | None = None,
        required_human_action: str = "",
    ) -> Issue:
        if self.counters.issues_created >= MAX_CREATED_ISSUES_PER_RUN:
            self.counters.warnings.append({"type": "created_issue_limit", "message": "Max created issues per run reached."})
            existing = self.db.execute(select(Issue).where(Issue.idempotency_key == key)).scalar_one_or_none()
            if existing is None:
                raise RuntimeError("Max created issues per run reached")
            return existing

        issue = self.db.execute(select(Issue).where(Issue.idempotency_key == key)).scalar_one_or_none()
        owner = self.assignments.agent(owner_name)
        reviewer = self.assignments.agent(reviewer_name)
        created = issue is None
        if issue is None:
            issue = Issue(title=title, description=description, issue_type=issue_type, status="backlog", idempotency_key=key)
            self.db.add(issue)
            self.db.flush()
            self.counters.issues_created += 1
            self.counters.created_issue_ids.append(issue.id)
            self._decision(issue, "issue_created", f"Created {title} from daily operating template.")
        elif self.counters.issues_updated < MAX_UPDATED_ISSUES_PER_RUN:
            self.counters.issues_updated += 1
            self.counters.updated_issue_ids.append(issue.id)

        issue.title = title
        issue.description = description
        issue.issue_type = issue_type
        issue.owner_agent_id = owner.id if owner else None
        issue.reviewer_agent_id = reviewer.id if reviewer else None
        issue.related_channel_id = channel.id if channel else issue.related_channel_id
        issue.priority = "high" if issue_type in {"review", "risk", "factcheck"} else "normal"
        issue.parent_issue_id = parent.id if parent else issue.parent_issue_id
        issue.root_issue_id = parent.root_issue_id or parent.id if parent else (issue.root_issue_id or issue.id)
        issue.delegation_level = (parent.delegation_level + 1) if parent else 0
        issue.target_metric = target_metric
        issue.target_value = float(target_value or 0)
        issue.current_value = float(current_value or 0)
        issue.next_action = next_action
        issue.required_human_action = required_human_action
        issue.progress_json = {**(issue.progress_json or {}), **progress, **issue_tree_progress(self.db, issue)}
        issue.blocked_reason = ""
        self._apply_assignment_blockers(issue)
        log_activity(
            self.db,
            actor_type="agent",
            actor_id=self.media_director.id if self.media_director else None,
            event_type="issue_created" if created else "issue_updated",
            entity_type="issue",
            entity_id=issue.id,
            message=("Created" if created else "Updated") + f" operating issue: {issue.title}",
            metadata={"idempotency_key": key, "target_metric": target_metric, "target_value": target_value},
        )
        return issue

    def _apply_assignment_blockers(self, issue: Issue) -> None:
        blocked = ""
        if not issue.owner_agent_id:
            blocked = "Owner agent is missing or disabled for this work type."
        elif not issue.reviewer_agent_id:
            blocked = "Reviewer agent is missing for supervised work."
        owner = self.db.get(OrgAgent, issue.owner_agent_id) if issue.owner_agent_id else None
        if owner and owner.name == "publisher_agent":
            blocked = "Publisher Agent is disabled; public publishing is not part of step 2.6."
        if issue.issue_type == "publish":
            blocked = "Publish issues are blocked until MAX publishing step and global publishing are enabled."
        issue.blocked_reason = blocked
        if blocked:
            issue.next_action = issue.next_action or "Resolve blocker before work can start."
            if "Publisher" in blocked or "Publish" in blocked:
                issue.required_human_action = "Do not create publishing work yet. Continue with review/planning only."

    def _refresh_issue_progress(self, issue: Issue) -> None:
        if issue.target_metric == "candidate_topics":
            issue.current_value = self._topics_today()
        elif issue.target_metric == "draft_candidates":
            channel = self.db.get(Channel, issue.related_channel_id) if issue.related_channel_id else None
            issue.current_value = self._posts_today(channel)
        elif issue.target_metric == "needs_review_processed":
            issue.target_value = self._needs_review_count()
            issue.current_value = 0
        elif issue.target_metric in {"risky_items_checked", "risk_reviews"}:
            issue.target_value = self._risky_items_count()
        elif issue.target_metric == "daily_content_plan":
            progress = issue_tree_progress(self.db, issue)
            issue.target_value = progress["sub_issues_total"] or 1
            issue.current_value = progress["sub_issues_terminal"]
        issue.progress_json = {**(issue.progress_json or {}), **issue_tree_progress(self.db, issue)}

    def _update_parent_progress(self, issue: Issue) -> None:
        self._refresh_issue_progress(issue)
        for child in self.db.execute(select(Issue).where(Issue.parent_issue_id == issue.id)).scalars():
            self._refresh_issue_progress(child)

    def _move(self, issue: Issue, target: str, reason: str) -> None:
        try:
            if self.kanban.transition(
                issue,
                target,
                actor_type="agent",
                actor_id=self.media_director.id if self.media_director else None,
                reason=reason,
                create_decision=True,
            ):
                self.counters.issues_moved += 1
                self.counters.moved_issue_ids.append(issue.id)
                self.counters.decisions_made += 1
        except ValueError as exc:
            self.counters.warnings.append({"type": "transition_rejected", "issue_id": issue.id, "message": str(exc)})

    def _move_to_waiting_human(self, issue: Issue, reason: str) -> None:
        if issue.status in {"waiting_human", "completed", "failed", "cancelled"}:
            return
        path = {
            "backlog": ["ready", "in_progress", "review", "waiting_human"],
            "ready": ["in_progress", "review", "waiting_human"],
            "in_progress": ["review", "waiting_human"],
            "review": ["waiting_human"],
        }.get(issue.status, [])
        for target in path:
            self._move(issue, target, reason)

    def _decision(self, issue: Issue, decision: str, reason: str) -> None:
        self.db.add(
            DecisionLog(
                issue_id=issue.id,
                entity_type="issue",
                entity_id=issue.id,
                decision=decision,
                reason=reason,
                confidence=0.86,
                alternatives_json=[{"allowed_next": allowed_transitions(issue.status)}],
            )
        )
        self.counters.decisions_made += 1

    def _topics_today(self) -> int:
        start = datetime.combine(datetime.now(UTC).date(), time.min, tzinfo=UTC)
        return int(self.db.scalar(select(func.count()).select_from(Topic).where(Topic.created_at >= start)) or 0)

    def _posts_today(self, channel: Channel | None = None) -> int:
        start = datetime.combine(datetime.now(UTC).date(), time.min, tzinfo=UTC)
        stmt = select(func.count()).select_from(Post).where(Post.created_at >= start)
        if channel:
            stmt = stmt.where(Post.channel_id == channel.id)
        return int(self.db.scalar(stmt) or 0)

    def _needs_review_count(self) -> int:
        return int(self.db.scalar(select(func.count()).select_from(Post).where(Post.status == "needs_review")) or 0)

    def _risky_items_count(self) -> int:
        risky_posts = self.db.scalar(select(func.count()).select_from(Post).where((Post.risk_score >= 0.6) | (Post.quality_score <= 0.4))) or 0
        risky_topics = self.db.scalar(select(func.count()).select_from(Topic).where(Topic.risk_score >= 0.6)) or 0
        return int(risky_posts) + int(risky_topics)

    def _runtime_exceeded(self) -> bool:
        return (datetime.now(UTC) - self.started_at).total_seconds() >= MAX_RUNTIME_SECONDS

    def _build_report(self, *, action: str, mode: str, planning_only: bool) -> dict[str, Any]:
        global_usage = daily_global_usage(self.db)
        media_usage = daily_agent_usage(self.db, self.media_director.id) if self.media_director else {"cost": 0, "tokens": 0}
        return {
            "action": action,
            "mode": mode,
            "planning_only": planning_only,
            "what_was_done": self._action_summary(action),
            "issues_created": self.counters.issues_created,
            "issues_updated": self.counters.issues_updated,
            "issues_moved": self.counters.issues_moved,
            "decisions_made": self.counters.decisions_made,
            "created_issue_ids": self.counters.created_issue_ids,
            "updated_issue_ids": self.counters.updated_issue_ids,
            "moved_issue_ids": self.counters.moved_issue_ids,
            "blocked": self.counters.human_input_issue_ids,
            "needs_human_input": self.counters.human_input_issue_ids,
            "next_suggested_action": self._next_suggested_action(),
            "budget_impact": {
                "global_cost_today": global_usage["cost"],
                "global_tokens_today": global_usage["tokens"],
                "media_director_cost_today": media_usage["cost"],
                "media_director_tokens_today": media_usage["tokens"],
                "external_llm_calls": 0,
            },
            "warnings": self.counters.warnings,
            "limits": {
                "max_iterations_per_run": MAX_ITERATIONS_PER_RUN,
                "max_created_issues_per_run": MAX_CREATED_ISSUES_PER_RUN,
                "max_updated_issues_per_run": MAX_UPDATED_ISSUES_PER_RUN,
                "max_llm_calls_per_run": 0 if planning_only else 5,
                "max_runtime_seconds": MAX_RUNTIME_SECONDS,
            },
        }

    @staticmethod
    def _action_summary(action: str) -> str:
        if action == "create_daily_plan":
            return "Created or updated the measurable daily content plan and delegated sub-issues."
        if action == "refresh_kanban":
            return "Updated issue progress, readiness and next actions."
        return "Checked blockers and human-input requirements."

    def _next_suggested_action(self) -> str:
        if self.counters.human_input_issue_ids:
            return "Resolve waiting_human issues before starting content-agent execution."
        if not self.settings.get("global_agents_enabled"):
            return "Review the Kanban plan, then enable global agents only when ready to run content tasks."
        return "Run specific content-agent tasks from ready issues; publishing remains disabled."
