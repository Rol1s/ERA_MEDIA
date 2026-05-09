from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models.all_models import AgentConfig, AgentRun, DecisionLog, Integration, Issue, Notification, OperatingLoopRun, OrgAgent, Post, PromptTemplate, Task
from app.seed import seed_channels, seed_integrations, seed_llm_control_plane, seed_org, seed_settings
from app.services.demo import create_demo_data
from app.agents.orchestrator import PipelineError, approve_post, schedule_post
from app.services.operating_loop import AgentOperatingLoop
from app.services.settings import get_settings


def ok(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"OK: {message}")


def main() -> None:
    seed_settings()
    seed_channels()
    seed_org()
    seed_integrations()
    seed_llm_control_plane()

    with SessionLocal() as db:
        settings = get_settings(db)
        ok(settings["system_mode"] == "mock", "mock mode is active")
        ok(not settings["global_publishing_enabled"], "public publishing is disabled")
        ok(not settings["global_agents_enabled"], "global agents are disabled by default")

        loop = AgentOperatingLoop(db).run(action="create_daily_plan", mode="manual_run")
        ok(loop.planning_only, "CEO loop runs planning-only while global agents are disabled")
        daily_issue_count = db.scalar(select(func.count()).select_from(Issue).where(Issue.idempotency_key.like("daily_content_plan:%"))) or 0
        ok(daily_issue_count >= 10, f"CEO loop creates or keeps measurable daily plan issues ({daily_issue_count})")
        ok(bool(loop.report_json.get("next_suggested_action")), "CEO loop writes operating report")
        daily_plan = db.execute(select(Issue).where(Issue.idempotency_key.like("daily_content_plan:%")).order_by(Issue.id.desc())).scalars().first()
        ok(daily_plan is not None and daily_plan.next_action, "daily plan issue has next_action")
        publisher_work = db.scalar(select(func.count()).select_from(Issue).join(OrgAgent, Issue.owner_agent_id == OrgAgent.id).where(OrgAgent.name == "publisher_agent")) or 0
        ok(publisher_work == 0, "publisher receives no work while disabled")

        integrations = db.scalar(select(func.count()).select_from(Integration)) or 0
        ok(integrations >= 8, f"integrations API data exists ({integrations})")

        org_agents = db.scalar(select(func.count()).select_from(OrgAgent)) or 0
        configs = db.scalar(select(func.count()).select_from(AgentConfig)) or 0
        ok(configs >= org_agents, f"agent config exists for every org agent ({configs}/{org_agents})")

        active_roles = db.execute(select(OrgAgent.role).distinct()).scalars().all()
        prompt_roles = db.execute(select(PromptTemplate.agent_type).where(PromptTemplate.status == "active").distinct()).scalars().all()
        missing_prompt_roles = sorted(set(active_roles) - set(prompt_roles) - {"board", "executive", "intelligence", "quality", "creative", "distribution", "growth"})
        ok(not missing_prompt_roles, f"prompt templates cover active agent types ({', '.join(prompt_roles)})")

        agent_run_high_water = db.scalar(select(func.coalesce(func.max(AgentRun.id), 0))) or 0
        result = create_demo_data(db)
        issue = db.execute(select(Issue).where(Issue.related_topic_id == result["topic_id"]).order_by(Issue.id.desc())).scalars().first()
        ok(issue is not None, "pipeline creates issue")
        ok(issue.status in {"review", "completed", "failed", "in_progress"}, f"issue kanban status is valid ({issue.status})")

        decisions = db.scalar(select(func.count()).select_from(DecisionLog).where(DecisionLog.issue_id == issue.id)) or 0
        notifications = db.scalar(select(func.count()).select_from(Notification).where(Notification.entity_type == "post")) or 0
        activity = db.scalar(select(func.count()).select_from(Task).where(Task.payload_json["issue_id"].as_integer() == issue.id)) or 0
        ok(decisions >= 1, f"decision logs created ({decisions})")
        ok(notifications >= 1, f"notification created for review ({notifications})")
        ok(activity >= 1, "task log attached to issue")

        publisher_runs = db.scalar(select(func.count()).select_from(AgentRun).where(AgentRun.agent_name == "publisher_agent")) or 0
        real_calls = db.scalar(
            select(func.count()).select_from(AgentRun).where(AgentRun.id > agent_run_high_water, AgentRun.provider != "mock")
        ) or 0
        running_tasks = db.scalar(select(func.count()).select_from(Task).where(Task.status == "running")) or 0
        ok(publisher_runs == 0, "publisher did not run")
        ok(real_calls == 0, "no real LLM call in mock mode")
        ok(running_tasks == 0, "no infinite/running tasks")

        post = db.get(Post, result["post_id"])
        ok(post is not None and post.status == "needs_review", "generated post is in review queue")
        ok(post.mock_only and bool(post.not_publishable_reason), "mock post is marked not publishable")
        ok(post.generation_mode == "mock" and not post.publishable, "mock post generation mode is explicit and not publishable")
        try:
            approve_post(db, post.id)
            raise AssertionError("Mock post approval should fail")
        except PipelineError:
            ok(True, "mock post cannot be approved for publishing")
        try:
            schedule_post(db, post.id)
            raise AssertionError("Mock post scheduling should fail")
        except PipelineError:
            ok(True, "mock post cannot be scheduled")
        loop_runs = db.scalar(select(func.count()).select_from(OperatingLoopRun)) or 0
        ok(loop_runs >= 1, "operating loop run is logged")

    print("SMOKE CONTROL PLANE PASSED")


if __name__ == "__main__":
    main()
