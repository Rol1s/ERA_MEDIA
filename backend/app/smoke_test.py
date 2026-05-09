from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models.all_models import AgentConfig, AgentRun, Channel, DecisionLog, Goal, Integration, Issue, LLMModel, Notification, OrgAgent, PlatformChannel, Post, PromptTemplate, Routine, Source, SystemSetting, Task, Topic
from app.seed import seed_channels, seed_integrations, seed_llm_control_plane, seed_org, seed_settings
from app.services.demo import create_demo_data


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    seed_settings()
    seed_channels()
    seed_org()
    seed_integrations()
    seed_llm_control_plane()
    with SessionLocal() as db:
        channel_count = db.scalar(select(func.count()).select_from(Channel).where(Channel.status == "active")) or 0
        assert_true(channel_count == 5, f"Expected 5 active channels, got {channel_count}")
        print("OK: 5 active channels")
        org_count = db.scalar(select(func.count()).select_from(OrgAgent)) or 0
        goal_count = db.scalar(select(func.count()).select_from(Goal)) or 0
        routine_count = db.scalar(select(func.count()).select_from(Routine)) or 0
        settings_count = db.scalar(select(func.count()).select_from(SystemSetting)) or 0
        integration_count = db.scalar(select(func.count()).select_from(Integration)) or 0
        platform_count = db.scalar(select(func.count()).select_from(PlatformChannel)) or 0
        agent_config_count = db.scalar(select(func.count()).select_from(AgentConfig)) or 0
        llm_model_count = db.scalar(select(func.count()).select_from(LLMModel)) or 0
        prompt_count = db.scalar(select(func.count()).select_from(PromptTemplate)) or 0
        assert_true(org_count >= 19, f"Expected org agents, got {org_count}")
        assert_true(goal_count >= 5, f"Expected goals, got {goal_count}")
        assert_true(routine_count >= 5, f"Expected routines, got {routine_count}")
        assert_true(settings_count >= 8, f"Expected system settings, got {settings_count}")
        assert_true(integration_count >= 6, f"Expected integrations, got {integration_count}")
        assert_true(platform_count >= 5, f"Expected platform channels, got {platform_count}")
        assert_true(agent_config_count >= org_count, f"Expected agent configs for every org agent, got {agent_config_count}/{org_count}")
        assert_true(llm_model_count >= 4, f"Expected LLM models, got {llm_model_count}")
        assert_true(prompt_count >= 5, f"Expected prompt templates, got {prompt_count}")
        print("OK: org agents, goals and routines are seeded")
        disabled_routines = db.scalar(select(func.count()).select_from(Routine).where(Routine.enabled.is_(False))) or 0
        publisher = db.execute(select(OrgAgent).where(OrgAgent.name == "publisher_agent")).scalar_one()
        budget = db.execute(select(SystemSetting).where(SystemSetting.key == "global_daily_budget_usd")).scalar_one()
        assert_true(disabled_routines >= 5, "Expected routines to be disabled by default")
        assert_true(publisher.status == "disabled", f"Publisher should be disabled, got {publisher.status}")
        assert_true(float(budget.value_json["value"]) == 2, f"Expected global budget $2, got {budget.value_json}")
        print("OK: safety defaults are locked")

        result = create_demo_data(db)
        print(f"OK: demo source #{result['source_id']}, topic #{result['topic_id']}, post #{result['post_id']}")

        source = db.get(Source, result["source_id"])
        topic = db.get(Topic, result["topic_id"])
        post = db.get(Post, result["post_id"])
        assert_true(source is not None, "Source was not created")
        assert_true(topic is not None, "Topic was not created")
        assert_true(post is not None, "Post was not created")
        assert_true(post.status == "needs_review", f"Expected post in needs_review, got {post.status}")
        assert_true(bool(post.source_urls), "Post has no source URLs")
        assert_true(post.mock_only, "Mock-mode post must be marked mock_only")
        print("OK: post appears in review queue with source URLs")

        agent_runs = db.scalar(select(func.count()).select_from(AgentRun).where(AgentRun.input_json["topic_id"].as_integer() == topic.id)) or 0
        tasks = db.scalar(select(func.count()).select_from(Task).where(Task.payload_json["topic_id"].as_integer() == topic.id)) or 0
        assert_true(agent_runs >= 4, f"Expected at least 4 agent runs, got {agent_runs}")
        assert_true(tasks >= 1, f"Expected at least 1 task log, got {tasks}")
        issues = db.scalar(select(func.count()).select_from(Issue).where(Issue.related_topic_id == topic.id)) or 0
        decisions = db.scalar(select(func.count()).select_from(DecisionLog).where(DecisionLog.entity_id == topic.id)) or 0
        notifications = db.scalar(select(func.count()).select_from(Notification).where(Notification.entity_type == "post")) or 0
        assert_true(issues >= 1, f"Expected at least 1 issue, got {issues}")
        assert_true(decisions >= 1, f"Expected decision logs, got {decisions}")
        assert_true(notifications >= 1, f"Expected notifications, got {notifications}")
        print(f"OK: {agent_runs} agent runs and {tasks} task logs")

        failed_running = db.scalar(select(func.count()).select_from(Task).where(Task.status == "running")) or 0
        assert_true(failed_running == 0, f"Expected no running tasks after smoke test, got {failed_running}")
        print("OK: no pipeline step is left running")

    print("SMOKE TEST PASSED")


if __name__ == "__main__":
    main()
