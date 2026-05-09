from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.all_models import AgentConfig, Channel, Goal, Integration, LLMModel, OrgAgent, PlatformChannel, PromptTemplate, Routine, SystemSetting

CHANNELS = [
    {
        "name": "ERA Сейчас",
        "slug": "era-now",
        "category": "news",
        "description": "Главные события дня коротко и спокойно.",
        "tone_of_voice": "Спокойно, кратко, без паники и кликбейта.",
        "audience_description": "Люди, которым нужно быстро понять, что произошло и почему это важно.",
        "topics_allowed": ["новости", "общество", "бизнес", "технологии", "повседневная жизнь"],
        "topics_forbidden": ["кликбейт", "паника", "неподтвержденные слухи"],
        "posting_frequency_per_day": 8,
        "daily_post_limit": 10,
        "publish_mode": "manual",
        "risk_threshold": 0.35,
    },
    {
        "name": "ERA Деньги",
        "slug": "era-money",
        "category": "money",
        "description": "Бизнес, личные финансы, предпринимательство и полезное денежное мышление.",
        "tone_of_voice": "Практично, трезво, предпринимательски, без фальшивой мотивации.",
        "audience_description": "Люди, которым нужны более сильные решения про деньги и бизнес.",
        "topics_allowed": ["бизнес", "личные финансы", "предпринимательство", "рыночный контекст"],
        "topics_forbidden": ["персональные инвестсоветы", "гарантированный доход", "торговые сигналы"],
        "posting_frequency_per_day": 4,
        "daily_post_limit": 5,
        "publish_mode": "manual",
        "risk_threshold": 0.3,
    },
    {
        "name": "ERA AI",
        "slug": "era-ai",
        "category": "ai",
        "description": "AI-инструменты, агенты, автоматизация, будущее работы и практическое применение.",
        "tone_of_voice": "Остро, практично, немного смело, с фокусом на пользу.",
        "audience_description": "Создатели, операторы и специалисты, которые используют AI в работе.",
        "topics_allowed": ["AI-инструменты", "автоматизация", "агенты", "будущее работы", "AI-бизнес"],
        "topics_forbidden": ["неподтвержденные заявления о моделях", "фейковые демо", "советы с риском приватности"],
        "posting_frequency_per_day": 5,
        "daily_post_limit": 6,
        "publish_mode": "semi_auto",
        "risk_threshold": 0.45,
    },
    {
        "name": "ERA Здоровье",
        "slug": "era-health",
        "category": "health",
        "description": "Сон, питание, энергия, привычки и простые объяснения исследований.",
        "tone_of_voice": "Осторожно, полезно, с уважением к доказательности, без диагнозов.",
        "audience_description": "Читатели, которым нужны аккуратные объяснения про здоровье на каждый день.",
        "topics_allowed": ["сон", "питание", "привычки", "энергия", "исследования здоровья"],
        "topics_forbidden": ["диагноз", "дозировки", "чудо-лечение", "хайп добавок"],
        "posting_frequency_per_day": 3,
        "daily_post_limit": 4,
        "publish_mode": "manual",
        "risk_threshold": 0.2,
    },
    {
        "name": "ERA Еда",
        "slug": "era-food",
        "category": "food",
        "description": "Рецепты, планирование еды, бюджетные блюда и простая полезная готовка.",
        "tone_of_voice": "Тепло, наглядно, практично, легко повторить.",
        "audience_description": "Люди, которым нужны простые и повторяемые идеи для еды.",
        "topics_allowed": ["рецепты", "планирование еды", "бюджетные блюда", "простая полезная готовка"],
        "topics_forbidden": ["опасная обработка еды", "экстремальные диеты", "медицинские заявления о питании"],
        "posting_frequency_per_day": 4,
        "daily_post_limit": 5,
        "publish_mode": "semi_auto",
        "risk_threshold": 0.4,
    },
]

DEFAULT_SETTINGS: dict[str, Any] = {
    "system_mode": "mock",
    "global_agents_enabled": False,
    "global_routines_enabled": False,
    "global_publishing_enabled": False,
    "global_daily_budget_usd": 2,
    "global_daily_token_limit": 100000,
    "require_human_approval_for_all_posts": True,
    "ui_language": "ru",
    "usd_to_rub_rate": 100,
    "admin_notification_provider": "none",
    "admin_notification_target": "",
    "notify_on_review_needed": True,
    "notify_on_failure": True,
    "notify_on_budget_warning": True,
}

INTEGRATIONS = [
    ("MAX Bot API", "max", "messenger", {"MAX_API_BASE_URL": "https://platform-api.max.ru", "default_admin_chat_id": "", "connected_channel_count": 0}, "MAX_BOT_TOKEN"),
    ("Mock LLM Provider", "mock", "llm", {"mode": "mock", "model": "mock"}, ""),
    ("OpenAI LLM Provider", "openai", "llm", {"model": "gpt-4.1-mini", "api": "responses", "structured_outputs": True}, "OPENAI_API_KEY"),
    ("Anthropic Claude Provider", "anthropic", "llm", {"model": "claude-3-5-haiku-latest", "api": "messages", "strict_tool_use": True}, "ANTHROPIC_API_KEY"),
    ("Gemini Provider", "gemini", "llm", {"model": "gemini-2.5-flash", "api": "generateContent", "structured_output": True}, "GEMINI_API_KEY"),
    ("Local Ollama Optional", "local_ollama_optional", "llm", {"model": "llama3.1", "local_only": True}, "OLLAMA_BASE_URL"),
    ("Admin Notifications", "webhook", "notification", {"target": "", "dry_run": True}, ""),
    ("Source Fetching", "rss", "source", {"enabled": True, "respect_paywalls": True}, ""),
    ("Storage", "storage", "storage", {"mode": "local"}, ""),
    ("Analytics", "analytics", "analytics", {"mode": "manual"}, ""),
]

LLM_MODELS = [
    ("mock", "mock", "Mock provider", 0, 0, False, True),
    ("openai", "gpt-5.5", "OpenAI GPT-5.5", 5.00, 30.00, True, True),
    ("openai", "gpt-5.5-pro", "OpenAI GPT-5.5 Pro", 30.00, 180.00, True, True),
    ("openai", "gpt-5.4", "OpenAI GPT-5.4", 2.50, 15.00, True, True),
    ("openai", "gpt-5.4-mini", "OpenAI GPT-5.4 mini", 0.75, 4.50, True, True),
    ("openai", "gpt-5.4-nano", "OpenAI GPT-5.4 nano", 0.20, 1.25, True, True),
    ("openai", "gpt-5.4-pro", "OpenAI GPT-5.4 Pro", 30.00, 180.00, True, True),
    ("openai", "gpt-4.1", "OpenAI GPT-4.1", 2.00, 8.00, True, True),
    ("openai", "gpt-4.1-mini", "OpenAI GPT-4.1 mini", 0.40, 1.60, True, True),
    ("openai", "gpt-4.1-nano", "OpenAI GPT-4.1 nano", 0.10, 0.40, True, True),
    ("openai", "gpt-4o", "OpenAI GPT-4o", 2.50, 10.00, True, True),
    ("openai", "gpt-4o-mini", "OpenAI GPT-4o mini", 0.15, 0.60, True, True),
    ("anthropic", "claude-opus-4-1-20250805", "Claude Opus 4.1", 15.00, 75.00, True, True),
    ("anthropic", "claude-opus-4-20250514", "Claude Opus 4", 15.00, 75.00, True, True),
    ("anthropic", "claude-sonnet-4-20250514", "Claude Sonnet 4", 3.00, 15.00, True, True),
    ("anthropic", "claude-3-7-sonnet-20250219", "Claude Sonnet 3.7", 3.00, 15.00, True, True),
    ("anthropic", "claude-3-7-sonnet-latest", "Claude Sonnet 3.7 latest", 3.00, 15.00, True, True),
    ("anthropic", "claude-3-5-haiku-20241022", "Claude Haiku 3.5", 0.80, 4.00, True, True),
    ("anthropic", "claude-3-5-haiku-latest", "Claude Haiku 3.5 latest", 0.80, 4.00, True, True),
    ("gemini", "gemini-3-pro-preview", "Gemini 3 Pro Preview", 2.00, 12.00, True, True),
    ("gemini", "gemini-3-flash-preview", "Gemini 3 Flash Preview", 0.50, 3.00, True, True),
    ("gemini", "gemini-2.5-pro", "Gemini 2.5 Pro", 1.25, 10.00, True, True),
    ("gemini", "gemini-2.5-flash", "Gemini 2.5 Flash", 0.30, 2.50, True, True),
    ("gemini", "gemini-2.5-flash-lite", "Gemini 2.5 Flash Lite", 0.10, 0.40, True, True),
    ("gemini", "gemini-2.0-flash", "Gemini 2.0 Flash", 0.10, 0.40, True, True),
    ("gemini", "gemini-2.0-flash-lite", "Gemini 2.0 Flash Lite", 0.075, 0.30, True, True),
    ("local_ollama_optional", "llama3.1", "Local Ollama llama3.1", 0, 0, False, True),
]

PROMPTS = [
    ("Editorial Director Prompt", "editorial", "You are ERA Editor-in-Chief. Enforce useful, sourced, non-clickbait editorial value. Variables: {{channel}} {{topic}}."),
    ("Editor Prompt", "editor", "Write a concise useful MAX post for {{channel}}. Add why it matters, practical angle, and source-aware wording."),
    ("Scout Prompt", "scout", "Normalize and score candidate topics. Reject boring rewrite-only items."),
    ("Factcheck Prompt", "factcheck", "Check source reliability, dates, unsupported claims, and risk. Escalate health/finance/legal/political risk."),
    ("Risk Prompt", "risk", "Detect financial, medical, legal, political, and reputational risks before publication."),
    ("Visual Prompt", "visual", "Create honest visual metadata without misleading claims."),
    ("Analytics Prompt", "analytics", "Summarize performance and recommend tomorrow content decisions."),
    ("Publisher Prompt", "publisher", "Prepare manual copy payloads only. Do not publish public content."),
]

PLAYBOOK_PROMPTS = [
    (
        "Research Agent Playbook Prompt",
        "scout",
        2,
        """You are ERA Research Agent. Use {{channel_playbook}} as the editorial brief for {{channel}}.
Return cautious source-backed JSON only. Extract what happened, why it matters, key facts, uncertainty, source URLs, suggested angles, and risk notes.
Do not invent facts. If source support is weak, say so plainly. Shape suggested angles to the channel formula and audience.""",
    ),
    (
        "Factcheck Agent Playbook Prompt",
        "factcheck",
        2,
        """You are ERA Factcheck Agent. Use {{channel_playbook}} and be stricter for news, money, and health.
Return JSON with factcheck_result, unsupported_claims, source_quality, source_date_if_available, human_review_required, reason, and risk_notes.
Score risk on 0-100. Escalate unsupported claims, stale sources, medical/financial advice, guarantees, and claims that need a human editor.""",
    ),
    (
        "Editor Agent Playbook Prompt",
        "editorial",
        2,
        """You are ERA Editor / Chief Editor depending on the requested JSON schema. Use {{channel_playbook}} exactly.
For EditorOutput: write a Russian MAX post with the channel required_structure, tone_of_voice, content pillars, banned patterns, CTA style, and max_post_length. Include why_useful, required_structure_used, and channel_playbook_checklist.
For ChiefEditorOutput: score editorial_value, factuality, clarity, usefulness, channel_fit, originality, risk, and overall quality on 0-100. Use decisions approve_for_review, rewrite_once, reject, or waiting_human. Never mark public publishing safe in Step 2.7.""",
    ),
    (
        "Risk Control Playbook Prompt",
        "risk",
        2,
        """You are ERA Risk Control Agent. Use {{channel_playbook}} to identify publication, medical, financial, legal, reputational, and source-quality risks.
Return structured risk notes only. Escalate anything that would require human approval. MAX public publishing remains disabled.""",
    ),
]

AGENT_DEFAULTS = {
    "human_owner": ("idle", 0, 0),
    "media_director": ("paused", 0.20, 20000),
    "intelligence_director": ("paused", 0.10, 15000),
    "world_scout_agent": ("paused", 0.50, 30000),
    "editor_in_chief": ("paused", 0.20, 20000),
    "news_editor_agent": ("paused", 0.15, 15000),
    "money_editor_agent": ("paused", 0.15, 15000),
    "ai_editor_agent": ("paused", 0.15, 15000),
    "health_editor_agent": ("paused", 0.15, 15000),
    "food_editor_agent": ("paused", 0.15, 15000),
    "quality_director": ("paused", 0.10, 12000),
    "factcheck_agent": ("paused", 0.20, 20000),
    "risk_control_agent": ("paused", 0.10, 10000),
    "creative_director": ("paused", 0.05, 8000),
    "visual_agent": ("paused", 0.10, 10000),
    "distribution_director": ("disabled", 0, 0),
    "publisher_agent": ("disabled", 0, 0),
    "growth_director": ("paused", 0.05, 8000),
    "analytics_agent": ("paused", 0.10, 10000),
}

ORG_AGENTS = [
    ("human_owner", "Board / Human Owner", "board", "human", None, "Human governance and final accountability.", ["Set strategy", "Approve sensitive policy", "Own budgets"], {"can_publish": False}, False, ""),
    ("media_director", "Media Director Agent", "executive", "director", "human_owner", "Runs the AI media factory and coordinates directors.", ["Coordinate media strategy", "Balance quality, speed and risk"], {"can_create_tasks": True}, True, "*/30 * * * *"),
    ("intelligence_director", "Intelligence Director Agent", "intelligence", "director", "media_director", "Owns topic discovery and source intelligence.", ["Manage discovery", "Prioritize sources"], {"can_collect_sources": True}, True, "0 */2 * * *"),
    ("world_scout_agent", "World Scout Agent", "scout", "agent", "intelligence_director", "Discovers, normalizes and clusters candidate topics.", ["Collect source items", "Cluster topics", "Route candidates"], {"can_create_topics": True}, True, "0 */3 * * *"),
    ("editor_in_chief", "Editor-in-Chief Agent", "editorial", "director", "media_director", "Owns editorial value and channel fit.", ["Set editorial standards", "Review post quality"], {"can_request_rewrite": True}, True, "*/45 * * * *"),
    ("news_editor_agent", "News Editor Agent", "editor", "agent", "editor_in_chief", "Writes concise context for ERA Сейчас.", ["Explain what happened", "Add why it matters"], {"channel": "era-now"}, True, "0 */2 * * *"),
    ("money_editor_agent", "Money Editor Agent", "editor", "agent", "editor_in_chief", "Writes practical money and business posts.", ["Avoid advice claims", "Add business implication"], {"channel": "era-money"}, True, "0 */3 * * *"),
    ("ai_editor_agent", "AI Editor Agent", "editor", "agent", "editor_in_chief", "Writes practical AI and automation posts.", ["Explain AI tools", "Add implementation angle"], {"channel": "era-ai"}, True, "0 */2 * * *"),
    ("health_editor_agent", "Health Editor Agent", "editor", "agent", "editor_in_chief", "Writes careful health explanations.", ["Avoid diagnosis", "Use evidence-aware wording"], {"channel": "era-health"}, True, "0 */4 * * *"),
    ("food_editor_agent", "Food Editor Agent", "editor", "agent", "editor_in_chief", "Writes useful food and cooking posts.", ["Make recipes repeatable", "Keep tone warm"], {"channel": "era-food"}, True, "0 */4 * * *"),
    ("quality_director", "Quality Director Agent", "quality", "director", "media_director", "Owns fact checks and risk gates.", ["Enforce source checks", "Escalate risk"], {"can_block_pipeline": True}, True, "*/30 * * * *"),
    ("factcheck_agent", "Factcheck Agent", "factcheck", "agent", "quality_director", "Checks sources, claims and dates.", ["Verify source references", "Stop unsupported claims"], {"can_reject": True}, True, "*/30 * * * *"),
    ("risk_control_agent", "Risk Control Agent", "risk", "agent", "quality_director", "Watches financial, health, legal and political risk.", ["Detect high risk", "Pause unsafe work"], {"can_pause_agents": True}, True, "*/30 * * * *"),
    ("creative_director", "Creative Director Agent", "creative", "director", "media_director", "Owns visual direction.", ["Shape visual prompts", "Keep channel identity"], {"can_generate_visual_prompts": True}, True, "0 */3 * * *"),
    ("visual_agent", "Visual Agent", "visual", "agent", "creative_director", "Creates visual prompts and metadata.", ["Prepare visual prompts", "Avoid misleading visuals"], {"can_generate_images": False}, True, "0 */4 * * *"),
    ("distribution_director", "Distribution Director Agent", "distribution", "director", "media_director", "Owns scheduling and publication readiness.", ["Prepare review queue", "Coordinate schedules"], {"can_schedule": True}, False, ""),
    ("publisher_agent", "Publisher Agent", "publisher", "agent", "distribution_director", "Prepares manual or semi-auto publication.", ["Do not publish without approval", "Prepare copy payloads"], {"can_auto_publish": False}, False, ""),
    ("growth_director", "Growth Director Agent", "growth", "director", "media_director", "Owns analytics and learning loops.", ["Read metrics", "Recommend improvements"], {"can_read_metrics": True}, True, "0 20 * * *"),
    ("analytics_agent", "Analytics Agent", "analytics", "agent", "growth_director", "Summarizes performance and recommendations.", ["Rank posts", "Recommend tomorrow topics"], {"can_update_recommendations": True}, True, "0 21 * * *"),
]

GOALS = [
    ("Publish 20 useful posts per day across all channels.", "Daily output target with editorial value.", "media_director", "useful_posts_per_day", 20),
    ("Keep high-risk posts under manual review.", "No risky content should bypass human review.", "quality_director", "high_risk_manual_review_rate", 1),
    ("Maintain zero infinite loops.", "All agent tasks must have max attempts and terminal states.", "media_director", "infinite_loop_count", 0),
    ("Keep daily LLM cost under configured budget.", "Stay within daily cost limits.", "growth_director", "daily_llm_cost", 2),
    ("Find at least 100 candidate topics per day.", "Maintain discovery pipeline depth.", "intelligence_director", "candidate_topics_per_day", 100),
]

ROUTINES = [
    ("Morning World Scout run", "Collect and cluster morning topics.", "world_scout_agent", "0 8 * * *", "world_scout_run", {"window": "morning"}),
    ("Midday news refresh", "Refresh important events around midday.", "news_editor_agent", "0 12 * * *", "news_refresh", {"window": "midday"}),
    ("Evening digest preparation", "Prepare evening digest candidates.", "editor_in_chief", "0 18 * * *", "evening_digest", {"window": "evening"}),
    ("Daily analytics report", "Summarize performance and recommendations.", "analytics_agent", "0 21 * * *", "daily_analytics_report", {}),
    ("Source health check", "Check source availability and freshness.", "intelligence_director", "0 */6 * * *", "source_health_check", {}),
]


def seed_settings() -> None:
    with SessionLocal() as db:
        for key, value in DEFAULT_SETTINGS.items():
            setting = db.execute(select(SystemSetting).where(SystemSetting.key == key)).scalar_one_or_none()
            if setting is None:
                db.add(SystemSetting(key=key, value_json={"value": value}))
            else:
                setting.value_json = {"value": value}
        db.commit()


def seed_channels() -> None:
    with SessionLocal() as db:
        for data in CHANNELS:
            channel = db.execute(select(Channel).where(Channel.slug == data["slug"])).scalar_one_or_none()
            if channel is None:
                channel = Channel(platform="max", status="active", auto_publish_enabled=False, **data)
                db.add(channel)
            for key, value in data.items():
                setattr(channel, key, value)
            channel.platform = "max"
            channel.status = "active"
            channel.auto_publish_enabled = False
        db.commit()


def seed_org() -> None:
    with SessionLocal() as db:
        agents_by_name: dict[str, OrgAgent] = {}
        for name, title, role, agent_type, _parent_name, description, responsibilities, permissions, heartbeat, cron in ORG_AGENTS:
            status, daily_budget, token_limit = AGENT_DEFAULTS[name]
            agent = db.execute(select(OrgAgent).where(OrgAgent.name == name)).scalar_one_or_none()
            if agent is None:
                agent = OrgAgent(name=name, title=title, role=role, agent_type=agent_type)
                db.add(agent)
                db.flush()
            agent.title = title
            agent.role = role
            agent.agent_type = agent_type
            agent.description = description
            agent.responsibilities = responsibilities
            agent.supervises = [item[0] for item in ORG_AGENTS if item[4] == name]
            agent.reviewed_by = _parent_name or ""
            agent.can_create_tasks = bool(permissions.get("can_create_tasks") or permissions.get("can_create_topics"))
            agent.can_approve_posts = name in {"human_owner", "editor_in_chief"}
            agent.can_publish = False
            agent.can_spend_budget = daily_budget > 0
            agent.permissions_json = permissions
            agent.budget_daily = daily_budget
            agent.budget_monthly = round(daily_budget * 30, 4)
            agent.token_limit_daily = token_limit
            agent.status = status
            agent.heartbeat_enabled = heartbeat
            agent.heartbeat_cron = cron
            agent.last_heartbeat_at = datetime.now(UTC) if heartbeat and agent.last_heartbeat_at is None else agent.last_heartbeat_at
            agents_by_name[name] = agent
        db.flush()

        for name, *_rest in ORG_AGENTS:
            parent_name = _rest[3]
            agent = agents_by_name[name]
            agent.parent_agent_id = agents_by_name[parent_name].id if parent_name else None

        for title, description, owner_name, metric, target in GOALS:
            goal = db.execute(select(Goal).where(Goal.title == title)).scalar_one_or_none()
            if goal is None:
                goal = Goal(title=title)
                db.add(goal)
            goal.description = description
            goal.owner_agent_id = agents_by_name[owner_name].id
            goal.target_metric = metric
            goal.target_value = target
            goal.current_value = 0
            goal.status = "active"

        for name, description, owner_name, cron, task_type, payload in ROUTINES:
            routine = db.execute(select(Routine).where(Routine.name == name)).scalar_one_or_none()
            if routine is None:
                routine = Routine(name=name)
                db.add(routine)
            routine.description = description
            routine.owner_agent_id = agents_by_name[owner_name].id
            routine.cron_schedule = cron
            routine.task_type = task_type
            routine.payload_json = payload
            routine.enabled = False
            routine.max_runs_per_day = 1
            routine.max_budget_per_run = 0.10
            routine.last_run_status = routine.last_run_status or "never"
            routine.next_run_at = routine.next_run_at or datetime.now(UTC) + timedelta(hours=1)

        db.commit()


def seed_integrations() -> None:
    with SessionLocal() as db:
        integrations_by_provider: dict[str, Integration] = {}
        for name, provider, type_, config, secret_ref in INTEGRATIONS:
            integration = db.execute(select(Integration).where(Integration.name == name)).scalar_one_or_none()
            if integration is None:
                integration = Integration(name=name, provider=provider, type=type_)
                db.add(integration)
                db.flush()
            integration.provider = provider
            integration.type = type_
            existing_config = dict(integration.config_json or {})
            if provider == "max" and existing_config.get("MAX_API_BASE_URL") == "https://botapi.max.ru":
                existing_config["MAX_API_BASE_URL"] = "https://platform-api.max.ru"
            integration.config_json = {**config, **existing_config}
            integration.secret_ref = integration.secret_ref or secret_ref
            integration.status = integration.status or "not_configured"
            integrations_by_provider[provider] = integration

        max_integration = integrations_by_provider.get("max")
        channels = db.execute(select(Channel).order_by(Channel.id)).scalars().all()
        for channel in channels:
            platform_channel = db.execute(
                select(PlatformChannel).where(
                    PlatformChannel.channel_id == channel.id,
                    PlatformChannel.platform == "max",
                )
            ).scalar_one_or_none()
            if platform_channel is None:
                platform_channel = PlatformChannel(channel_id=channel.id, platform="max")
                db.add(platform_channel)
            platform_channel.integration_id = max_integration.id if max_integration else None
            platform_channel.publish_mode = "manual_copy" if channel.publish_mode == "manual" else "semi_auto_approval"
            platform_channel.can_publish = False
            platform_channel.status = platform_channel.status or "not_connected"
        db.commit()


def seed_llm_control_plane() -> None:
    with SessionLocal() as db:
        for provider, model, label, input_cost, output_cost, supports_tools, supports_json_schema in LLM_MODELS:
            item = db.execute(select(LLMModel).where(LLMModel.provider == provider, LLMModel.model == model)).scalar_one_or_none()
            if item is None:
                item = LLMModel(provider=provider, model=model)
                db.add(item)
            item.label = label
            item.input_cost_per_1m = input_cost
            item.output_cost_per_1m = output_cost
            item.supports_tools = supports_tools
            item.supports_json_schema = supports_json_schema
            item.enabled = True

        agents = db.execute(select(OrgAgent).order_by(OrgAgent.id)).scalars().all()
        for agent in agents:
            config = db.execute(select(AgentConfig).where(AgentConfig.org_agent_id == agent.id)).scalar_one_or_none()
            if config is None:
                config = AgentConfig(org_agent_id=agent.id)
                db.add(config)
            config.provider = config.provider or "mock"
            config.model = config.model or "mock"
            config.temperature = config.temperature if config.temperature is not None else 0.2
            config.max_tokens = config.max_tokens or 800
            config.system_prompt = config.system_prompt or f"You are {agent.title} in ERA Media Factory. Follow safety, budget and editorial-value rules."
            config.tools_json = config.tools_json or []
            config.daily_budget_usd = config.daily_budget_usd or agent.budget_daily
            config.daily_token_limit = config.daily_token_limit or agent.token_limit_daily
            if agent.name == "world_scout_agent":
                config.max_runs_per_day = config.max_runs_per_day or 1
            elif agent.role == "editor":
                config.max_runs_per_day = config.max_runs_per_day or 5
            elif agent.name == "factcheck_agent":
                config.max_runs_per_day = config.max_runs_per_day or 10
            else:
                config.max_runs_per_day = config.max_runs_per_day or 3
            config.timeout_seconds = config.timeout_seconds or 30
            config.enabled = config.enabled if config.enabled is not None else False

        for name, agent_type, content in PROMPTS:
            existing = db.execute(
                select(PromptTemplate).where(PromptTemplate.name == name, PromptTemplate.agent_type == agent_type, PromptTemplate.version == 1)
            ).scalar_one_or_none()
            if existing is None:
                db.add(
                    PromptTemplate(
                        name=name,
                        agent_type=agent_type,
                        version=1,
                        content=content,
                        variables_json={"channel": "Channel profile", "topic": "Topic/research context"},
                        status="active",
                    )
                )

        for name, agent_type, version, content in PLAYBOOK_PROMPTS:
            existing = db.execute(
                select(PromptTemplate).where(
                    PromptTemplate.name == name,
                    PromptTemplate.agent_type == agent_type,
                    PromptTemplate.version == version,
                )
            ).scalar_one_or_none()
            if existing is None:
                existing = PromptTemplate(name=name, agent_type=agent_type, version=version)
                db.add(existing)
            existing.content = content
            existing.variables_json = {
                "channel": "Channel name",
                "topic": "Topic title",
                "channel_playbook": "Channel editorial playbook and safety gates",
                "playbook": "Alias for channel_playbook",
            }
            existing.status = "active"
            for other in db.execute(
                select(PromptTemplate).where(
                    PromptTemplate.agent_type == agent_type,
                    PromptTemplate.id != existing.id,
                    PromptTemplate.status == "active",
                )
            ).scalars():
                other.status = "archived"
        db.commit()


if __name__ == "__main__":
    seed_settings()
    seed_channels()
    seed_org()
    seed_integrations()
    seed_llm_control_plane()
