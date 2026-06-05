export const API_URL = "";

export type ApiStatus = {
  status: string;
  service: string;
  database_ok: boolean;
  active_channels: number;
  dev_mode: boolean;
  system_mode: "mock" | "dry_run" | "live" | "production_manual" | "production_auto";
  runtime_mode?: "MOCK" | "DRY_RUN" | "LIVE_INTERNAL" | "AUTO_LIVE";
  global_agents_enabled: boolean;
  global_routines_enabled: boolean;
  global_publishing_enabled: boolean;
};

export type Channel = {
  id: number;
  name: string;
  slug: string;
  category: string;
  description: string;
  tone_of_voice: string;
  audience_description: string;
  topics_allowed: string[];
  topics_forbidden: string[];
  posting_frequency_per_day: number;
  daily_post_limit: number;
  publish_mode: "manual" | "semi_auto" | "auto";
  auto_publish_enabled: boolean;
  risk_threshold: number;
  channel_mode?: "newsroom" | "relay" | string;
  relay_mode?: "single_source_live" | "multi_source_live" | string;
  relay_source_ids?: number[];
  relay_publish_delay_minutes?: number;
  relay_max_posts_per_day?: number;
  status: string;
};

export type RelayChannel = {
  id: number;
  name: string;
  slug: string;
  status: string;
  auto_publish_enabled: boolean;
  relay_mode: string;
  relay_source_ids: number[];
  relay_max_posts_per_day: number;
  relay_publish_delay_minutes: number;
  sources: { id: number; name: string; url: string; status: string }[];
  max: { chat_id: string; url: string; status: string; can_publish: boolean };
  has_posts: boolean;
  last_run?: { created_at?: string | null; message: string; metadata: Record<string, any> };
  recent_posts?: { id: number; status: string; title: string; created_at?: string | null; published_at?: string | null; source_urls: string[] }[];
};

export type EditorialDirectorMessage = {
  id: number;
  session_id: number;
  role: "user" | "assistant" | string;
  content: string;
  payload: Record<string, any>;
  created_at: string;
};

export type EditorialDirectorSession = {
  id: number;
  title: string;
  status: string;
  mode: string;
  command: string;
  summary: string;
  report: Record<string, any>;
  created_issue_ids: number[];
  requires_human_confirmation: boolean;
  created_at: string;
  updated_at: string;
  messages?: EditorialDirectorMessage[];
};

export type Source = {
  id: number;
  name: string;
  url: string;
  resolved_url?: string;
  rsshub_route?: string;
  type: string;
  language: string;
  trust_score: number;
  check_interval_minutes: number;
  last_checked_at?: string | null;
  requires_review: boolean;
  last_error: string;
  health_status: string;
  is_demo: boolean;
  status: string;
  source_priority: string;
  source_quality_tier: string;
  poll_interval_minutes: number;
  last_poll_at?: string | null;
  next_poll_at?: string | null;
  breaking_monitor_enabled: boolean;
  reliability_score: number;
  speed_score: number;
  noise_score: number;
  ingestion_enabled: boolean;
  requires_operator_approval: boolean;
  channel_ids: number[];
  items_count?: number;
  valid_items_count?: number;
  duplicate_items_count?: number;
  failed_items_count?: number;
  created_at?: string | null;
  updated_at?: string | null;
};

export type Topic = {
  id: number;
  source_id?: number | null;
  source_item_id?: number | null;
  title: string;
  url?: string | null;
  raw_text?: string;
  summary: string;
  freshness_score?: number;
  urgency_score?: number;
  novelty_score?: number;
  first_detected_at?: string | null;
  latest_source_at?: string | null;
  freshness_status?: "breaking" | "fresh" | "developing" | "newly_discovered_reference" | "evergreen" | "stale" | "unknown_date";
  freshness_reason?: string;
  story_cluster_id?: string;
  content_age_minutes?: number;
  detection_age_minutes?: number;
  is_new_to_system?: boolean;
  is_new_in_world?: boolean;
  freshness_basis?: string;
  content_type?: string;
  relevance_score?: number;
  content_length?: number;
  extraction_status?: string;
  extraction_error?: string;
  language?: string;
  source_published_at?: string | null;
  source_updated_at?: string | null;
  canonical_url?: string;
  paywall_or_blocked_detected?: boolean;
  final_score: number;
  usefulness_score: number;
  originality_score: number;
  source_trust_score: number;
  why_this_matters: string;
  suggested_angle: string;
  assigned_channel_ids: number[];
  is_duplicate: boolean;
  is_demo: boolean;
  risk_score: number;
  status: string;
  created_at: string;
  updated_at?: string;
};

export type SourceItem = {
  id: number;
  source_id: number;
  url: string;
  canonical_url: string;
  title: string;
  summary: string;
  extracted_text: string;
  extracted_summary: string;
  published_at?: string | null;
  source_updated_at?: string | null;
  detected_at: string;
  language: string;
  content_length: number;
  extraction_status: string;
  extraction_error: string;
  paywall_or_blocked_detected: boolean;
  duplicate_of_item_id?: number | null;
  first_seen_at?: string | null;
  last_seen_at?: string | null;
  age_minutes?: number;
  content_age_minutes?: number;
  detection_age_minutes?: number;
  freshness_score?: number;
  source_priority?: string;
  is_breaking_candidate?: boolean;
  is_stale?: boolean;
  is_new_to_system?: boolean;
  is_new_in_world?: boolean;
  freshness_basis?: string;
  content_type?: string;
  freshness_reason?: string;
  story_cluster_id?: string;
  linked_topic_id?: number | null;
  created_at: string;
  updated_at: string;
};

export type SourceFetchResult = {
  source_id: number;
  fetched_count: number;
  extracted_count: number;
  topics_created: number;
  duplicates: number;
  blocked: number;
  failed: number;
  source_item_ids: number[];
  topic_ids: number[];
  last_error: string;
};

export type DailyEdition = {
  id: number;
  date: string;
  channel_id: number;
  channel_name: string;
  channel_slug: string;
  status: string;
  target_topics_count: number;
  target_posts_count: number;
  selected_topics_count: number;
  generated_posts_count: number;
  approved_posts_count: number;
  rejected_posts_count: number;
  editor_notes: string;
  cost: number;
  next_action: string;
  created_at: string;
  updated_at: string;
};

export type EditionDetail = {
  edition: DailyEdition;
  sources: Source[];
  candidate_topics: Topic[];
  selected_topics: Topic[];
  rejected_topics: Topic[];
  generated_posts: Post[];
  final_pack_posts: Post[];
  rejected_posts: Post[];
};

export type Post = {
  id: number;
  channel_id: number;
  topic_id?: number | null;
  daily_edition_id?: number | null;
  title: string;
  body: string;
  visual_prompt: string;
  source_urls: string[];
  visual_type: string;
  visual_safety_notes: string;
  image_generation_allowed: boolean;
  image_generation_status: string;
  image_url?: string | null;
  post_type?: "NEWS" | "EXPLAINER" | "DIGEST" | "UPDATE" | "ALERT" | string;
  novelty_score?: number;
  dedup_decision_json?: Record<string, any>;
  quality_verdict?: string;
  status: string;
  risk_score: number;
  quality_score: number;
  status_reason: string;
  risk_reason: string;
  quality_reason: string;
  scheduled_at?: string | null;
  version: number;
  version_history: Record<string, any>[];
  published_at?: string | null;
  published_url?: string;
  manual_publish_note?: string;
  is_demo: boolean;
  mock_only: boolean;
  not_publishable_reason: string;
  generation_mode: "mock" | "dry_run" | "live";
  provider: string;
  model: string;
  prompt_template_version?: number | null;
  publishable: boolean;
  non_publishable_reason: string;
  tokens_input: number;
  tokens_output: number;
  estimated_cost_usd: number;
  llm_trace_id?: string | null;
  structured_outputs_json: Record<string, any>;
  media_source_type?: "source_preview" | "official" | "generated" | "manual" | "none" | string;
  media_source_url?: string;
  media_rights_note?: string;
  media_status?: "missing" | "found" | "generated" | "needs_review" | "approved" | "failed" | string;
  max_packaged_text?: string;
  max_buttons_json?: Record<string, any>;
  operator_checklist_json?: Record<string, any>;
  created_at?: string;
  updated_at?: string;
};

export type EditorDayToday = {
  status: string;
  morning_scan?: EditorialDirectorSession | null;
  agenda?: EditorialDirectorSession | null;
  counts: Record<string, number>;
  write_now: Topic[];
  watchlist: Topic[];
  posts: Post[];
};

export type NewsroomSubmission = {
  id: number;
  status: string;
  source: string;
  submitter_chat_id: string;
  submitter_name: string;
  text: string;
  url: string;
  media_url: string;
  topic_id?: number | null;
  rejected_reason: string;
  created_at: string;
  updated_at: string;
};

export type Task = {
  id: number;
  task_type: string;
  payload_json?: Record<string, any>;
  status: string;
  attempts: number;
  max_attempts: number;
  error_message?: string | null;
};

export type AgentRun = {
  id: number;
  agent_name: string;
  task_type: string;
  input_json: Record<string, any>;
  output_json: Record<string, any>;
  status: string;
  tokens_input: number;
  tokens_output: number;
  estimated_cost: number;
  provider: string;
  model: string;
  prompt_template_id?: number | null;
  prompt_version?: number | null;
  error_message?: string | null;
  skill_contract_id?: number | null;
  task_contract_id?: number | null;
  contract_version_id?: number | null;
  contract_version: string;
  schema_version: string;
  skill_version: string;
  prompt_template_version: string;
  input_contract_json: Record<string, any>;
  output_contract_json: Record<string, any>;
  handoff_contract_json: Record<string, any>;
  validation_result_json: Record<string, any>;
  escalation_contract_json: Record<string, any>;
  raw_response_json: Record<string, any>;
  latency_ms: number;
  queue_wait_ms: number;
  retries: number;
  next_agent: string;
  next_action: string;
};

export type BrainStatus = {
  brain: { mode: "local_gemma" | "openai" | string; provider: string; model: string };
  health: Record<string, any>;
  rollback: { available: boolean; automatic_fallback: boolean; message: string };
  publishing: { max_publishing_enabled: boolean; autopublish_enabled: boolean };
};

export type BrainMigrationPreview = {
  provider: string;
  model: string;
  changes: number;
  affected: {
    agent_id: number;
    agent_name: string;
    config_id: number;
    will_change: boolean;
    before: Record<string, any>;
    after: Record<string, any>;
    preserved: string[];
  }[];
};

export type AgentWorkbenchContracts = {
  agent_skill_contracts: Record<string, any>[];
  contract_templates: Record<string, any>[];
  contract_versions: Record<string, any>[];
};

export type MissionControlState =
  | "queued"
  | "model_generating"
  | "tool_calling"
  | "waiting_io"
  | "waiting_human"
  | "retrying"
  | "completed"
  | "failed"
  | "stalled"
  | "active"
  | "idle";

export type MissionControlStep = {
  id: string;
  type: string;
  state: MissionControlState | string;
  agent: string;
  task_type: string;
  entity: Record<string, any>;
  current_step: string;
  decision_summary: string;
  last_action: string;
  next_action: string;
  blocked_reason: string;
  provider?: string;
  model?: string;
  latency_ms?: number;
  queue_wait_ms?: number;
  started_at?: string | null;
  finished_at?: string | null;
  updated_at?: string | null;
  review_context?: Record<string, any>;
};

export type MissionControlReadModel = {
  generated_at: string;
  mission: {
    state: MissionControlState | string;
    current_step: string;
    decision_summary: string;
    last_action: string;
    next_action: string;
    blocked_reason: string;
  };
  brain: { provider: string; queue: Record<string, any> };
  state_counts: Record<string, number>;
  pipeline: Record<string, any>[];
  missions: Record<string, any>[];
  topics: Record<string, any>[];
  posts: Record<string, any>[];
  tasks: MissionControlStep[];
  agent_runs: MissionControlStep[];
  steps: MissionControlStep[];
  llm_calls: Record<string, any>[];
  tool_calls: MissionControlStep[];
  artifacts: Record<string, any>[];
  human_decisions: Record<string, any>[];
  activity: ActivityEvent[];
  agents: OrgAgent[];
};

export type StyleLintResult = {
  passed: boolean;
  score: number;
  issues: { code: string; message: string; severity: string }[];
  rewrite_required: boolean;
};

export type OrgAgent = {
  id: number;
  name: string;
  title: string;
  role: string;
  agent_type: string;
  parent_agent_id?: number | null;
  description: string;
  responsibilities: string[];
  supervises: string[];
  reviewed_by: string;
  can_create_tasks: boolean;
  can_approve_posts: boolean;
  can_publish: boolean;
  can_spend_budget: boolean;
  permissions_json: Record<string, any>;
  budget_daily: number;
  budget_monthly: number;
  token_limit_daily: number;
  status: string;
  heartbeat_enabled: boolean;
  heartbeat_cron: string;
  last_heartbeat_at?: string | null;
  daily_cost_used: number;
  daily_tokens_used: number;
  budget_warning: boolean;
  current_thought?: string | null;
  current_summary?: string | null;
  active_run_id?: number | null;
  active_task_id?: number | null;
  active_topic_id?: number | null;
  active_post_id?: number | null;
  needs_human?: boolean;
  human_action_required?: string | null;
  blockers_json?: any[] | null;
  daily_cost_cached?: number | null;
  daily_tokens_cached?: number | null;
};

export type Integration = {
  id: number;
  name: string;
  provider: string;
  type: string;
  status: string;
  config_json: Record<string, any>;
  secret_ref: string;
  secret_configured: boolean;
  required_env_template: string;
  last_check_at?: string | null;
  last_success_at?: string | null;
  last_error: string;
};

export type PlatformChannel = {
  id: number;
  channel_id: number;
  platform: string;
  external_chat_id: string;
  external_channel_url: string;
  integration_id?: number | null;
  status: string;
  publish_mode: "manual_copy" | "semi_auto_approval" | "auto_publish";
  can_publish: boolean;
  last_test_at?: string | null;
  last_success_at?: string | null;
  last_error: string;
};

export type MaxDiscoveredChat = {
  chat_id?: string | number | null;
  title?: string | null;
  type?: string | null;
  status?: string | null;
  link?: string | null;
  is_public?: boolean | null;
  participants_count?: number | null;
};

export type ChannelWorkspace = {
  channel: Channel;
  platform_channel?: PlatformChannel | null;
  stats: {
    sources: number;
    active_sources: number;
    topics: number;
    topics_today: number;
    drafts: number;
    approved: number;
    published: number;
  };
  source_coverage: {
    status: "empty" | "thin" | "degraded" | "ok" | string;
    recommendation: string;
    total_sources: number;
    active_sources: number;
    failed_sources: number;
    items_today: number;
    category: string;
  };
  sources: Source[];
  suggested_sources: { source: Source; fit_score: number; reason: string }[];
  radar: Topic[];
  topics: Topic[];
  posts: Post[];
  last_activity: { id: number; event_type: string; message: string; created_at: string; metadata: Record<string, any> }[];
};

export type StartMaxChannelResult = {
  ok: boolean;
  channel: Channel;
  platform_channel: PlatformChannel;
  max_called: boolean;
  published: boolean;
};

export type ChannelUrlIngestResult = {
  ok: boolean;
  channel_id: number;
  created_source: boolean;
  source: Source;
  result: SourceFetchResult;
  topics: Topic[];
  llm_called: boolean;
  max_called: boolean;
  published: boolean;
};

export type NotificationItem = {
  id: number;
  severity: "info" | "warning" | "critical";
  title: string;
  message: string;
  entity_type: string;
  entity_id?: number | null;
  status: "unread" | "read" | "archived";
  created_at: string;
  read_at?: string | null;
};

export type Issue = {
  id: number;
  parent_issue_id?: number | null;
  root_issue_id?: number | null;
  delegation_level: number;
  blocked_by_issue_id?: number | null;
  title: string;
  description: string;
  issue_type: string;
  owner_agent_id?: number | null;
  reviewer_agent_id?: number | null;
  related_channel_id?: number | null;
  related_topic_id?: number | null;
  related_post_id?: number | null;
  priority: string;
  status: string;
  next_action: string;
  blocked_reason: string;
  required_human_action: string;
  target_metric: string;
  target_value: number;
  current_value: number;
  progress_json: Record<string, any>;
  idempotency_key?: string | null;
  sub_issue_count: number;
  result_summary: string;
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
};

export type IssueDetail = {
  issue: Issue;
  parent?: Issue | null;
  sub_issues: Issue[];
  allowed_transitions: string[];
  progress: Record<string, any>;
  decision_logs: DecisionLog[];
  activity: ActivityEvent[];
};

export type OperatingLoopRun = {
  id: number;
  mode: "manual_run" | "dry_run" | "scheduled";
  action: "create_daily_plan" | "refresh_kanban" | "check_blockers";
  planning_only: boolean;
  status: string;
  report_json: Record<string, any>;
  issues_created: number;
  issues_updated: number;
  issues_moved: number;
  decisions_made: number;
  warnings_json: Record<string, any>[];
  started_at: string;
  finished_at?: string | null;
  error_message: string;
};

export type AgencyOperatingReport = {
  overall_status: "ready" | "degraded" | "blocked";
  blockers: string[];
  warnings: string[];
  recommended_tasks: Record<string, any>[];
  human_actions_required: Record<string, any>[];
  next_best_action: string;
  infrastructure: Record<string, any>;
  channels: Record<string, any>[];
  sources: Record<string, any>;
  radar: Record<string, any>;
  editorial_flow: Record<string, any>;
  safety: Record<string, any>;
  generated_at: string;
};

export type MediaDirectorLoopResult = {
  status: string;
  created_issues: number[];
  updated_issues: number[];
  delegated_tasks: Record<string, any>[];
  human_actions_required: number[];
  operating_summary: string;
  agency_report: AgencyOperatingReport;
  safety: Record<string, any>;
};

export type LLMModel = {
  id: number;
  provider: string;
  model: string;
  label: string;
  input_cost_per_1m: number;
  output_cost_per_1m: number;
  supports_tools: boolean;
  supports_json_schema: boolean;
  enabled: boolean;
};

export type AgentConfig = {
  id: number;
  org_agent_id: number;
  prompt_template_id?: number | null;
  provider: string;
  model: string;
  temperature: number;
  max_tokens: number;
  system_prompt: string;
  tools_json: Record<string, any>[];
  daily_budget_usd: number;
  daily_token_limit: number;
  max_runs_per_day: number;
  timeout_seconds: number;
  enabled: boolean;
};

export type AgentRoleFilePreview = {
  version: number;
  total: number;
  items: {
    agent_id: number;
    agent_name: string;
    title: string;
    config_id: number;
    role_file: string;
    prompt_name: string;
    prompt_template_id?: number | null;
    current_prompt_len: number;
    new_prompt_len: number;
    provider: string;
    model: string;
    will_change_prompt: boolean;
    preserved: string[];
  }[];
};

export type PromptTemplate = {
  id: number;
  name: string;
  agent_type: string;
  version: number;
  content: string;
  variables_json: Record<string, any>;
  status: "draft" | "active" | "archived";
};

export type ButtonContract = {
  page: string;
  label: string;
  component_id: string;
  endpoint: string;
  method: string;
  payload_schema: Record<string, any>;
  expected_success_status: number;
  creates_activity_event: boolean;
  action_type: string;
  expected_state_change: string;
  implemented: boolean;
  last_tested_at?: string | null;
};

export type ExplainResult = {
  entity_type: string;
  entity_id: number;
  source_input: Record<string, any>;
  agent_chain: Record<string, any>[];
  decisions: DecisionLog[];
};

export type AgentDetail = {
  agent: Partial<OrgAgent> & { id: number; name: string; title: string; role: string; status: string };
  telemetry?: AgentTelemetry | null;
  config?: AgentConfig | null;
  prompt_template?: PromptTemplate | null;
  recent_agent_runs: AgentRun[];
  recent_issues: Issue[];
  recent_decision_logs: DecisionLog[];
  recent_activity: ActivityEvent[];
  budget_usage: { cost: number; tokens: number };
  provider_readiness?: Record<string, any>;
};

export type DecisionLog = {
  id: number;
  agent_run_id?: number | null;
  issue_id?: number | null;
  entity_type: string;
  entity_id?: number | null;
  decision: string;
  reason: string;
  confidence: number;
  alternatives_json: Record<string, any>[];
  created_at: string;
};

export type AgentTelemetry = {
  id: number;
  name: string;
  title: string;
  status: string;
  runs_today: number;
  success_rate: number;
  avg_duration_seconds: number;
  tokens_today: number;
  cost_today: number;
  last_error: string;
  current_issue?: string | null;
};

export type Goal = {
  id: number;
  title: string;
  description: string;
  owner_agent_id?: number | null;
  target_metric: string;
  target_value: number;
  current_value: number;
  status: string;
};

export type Routine = {
  id: number;
  name: string;
  description: string;
  owner_agent_id?: number | null;
  cron_schedule: string;
  task_type: string;
  payload_json: Record<string, any>;
  enabled: boolean;
  max_runs_per_day: number;
  max_budget_per_run: number;
  last_run_status: string;
  last_run_at?: string | null;
  next_run_at?: string | null;
};

export type ActivityEvent = {
  id: number;
  actor_type: string;
  actor_id?: number | null;
  event_type: string;
  entity_type: string;
  entity_id?: number | null;
  message: string;
  metadata_json: Record<string, any>;
  created_at: string;
};

export type CostSummary = {
  total_estimated_cost_today: number;
  total_estimated_cost_today_rub: number;
  budget_daily_total: number;
  budget_daily_total_rub: number;
  budget_remaining: number;
  budget_remaining_rub: number;
  rub_rate: number;
  by_agent: Record<string, number>;
  by_channel: Record<string, number>;
  by_task_type: Record<string, number>;
  budget_warnings: OrgAgent[];
};

export type SystemSettings = {
  system_mode: "mock" | "dry_run" | "live" | "production_manual" | "production_auto";
  ai_brain_mode?: "local_gemma" | "openai" | string;
  ai_brain_provider?: string;
  ai_brain_model?: string;
  ollama_base_url?: string;
  openai_blocked_in_local_mode?: boolean;
  mock_blocked_in_operator_path?: boolean;
  store_raw_llm_response?: boolean;
  real_newsroom_mode: boolean;
  global_agents_enabled: boolean;
  global_routines_enabled: boolean;
  global_publishing_enabled: boolean;
  global_daily_budget_usd: number;
  global_daily_token_limit: number;
  require_human_approval_for_all_posts: boolean;
  ui_language: "ru" | "en";
  usd_to_rub_rate: number;
  admin_notification_provider: "none" | "max" | "telegram" | "webhook";
  admin_notification_target: string;
  notify_on_review_needed: boolean;
  notify_on_failure: boolean;
  notify_on_budget_warning: boolean;
  daily_usage?: { cost: number; tokens: number };
};

export type LaunchReadiness = {
  overall_status: "ready" | "degraded" | "blocked";
  blockers: string[];
  warnings: string[];
  content_counts: Record<string, number>;
  mode_state: Record<string, any>;
  connector_state: Record<string, any>;
  pipeline_state: Record<string, any>;
  safety_state: Record<string, any>;
  next_actions: string[];
};

export type GrowthCampaign = {
  id: number;
  name: string;
  target_channel_id?: number | null;
  target_channel?: Channel | null;
  goal: string;
  offer: string;
  audience: string;
  tone: string;
  risk_level: string;
  status: string;
  hypothesis_json: Record<string, any>;
  kpi_json: Record<string, any>;
  created_at: string;
  updated_at: string;
};

export type FunnelAsset = {
  id: number;
  campaign_id: number;
  post_id?: number | null;
  asset_type: string;
  platform: string;
  title: string;
  text: string;
  cta: string;
  target_url: string;
  risk_notes: string;
  status: string;
  metadata_json: Record<string, any>;
  created_at: string;
  updated_at: string;
};

export type TrafficSource = {
  id: number;
  name: string;
  platform: string;
  category: string;
  url: string;
  risk_level: string;
  notes: string;
  status: string;
  created_at: string;
  updated_at: string;
};

export type SeedingRun = {
  id: number;
  campaign_id: number;
  asset_id?: number | null;
  traffic_source_id?: number | null;
  platform: string;
  placements_count: number;
  link_clicks: number;
  joins: number;
  bans: number;
  complaints: number;
  result: string;
  notes: string;
  created_at: string;
  updated_at: string;
};

export type GrowthDashboard = {
  campaigns: GrowthCampaign[];
  assets: FunnelAsset[];
  traffic_sources: TrafficSource[];
  seeding_runs: SeedingRun[];
  totals: Record<string, number>;
  safety: Record<string, any>;
};

export type GrowthPackResult = {
  post_id?: number | null;
  landing_asset: FunnelAsset;
  seed_comments: FunnelAsset[];
  dashboard: GrowthDashboard;
};

export type PostMetric = {
  id: number;
  post_id: number;
  channel_id?: number | null;
  published_at?: string | null;
  views: number;
  reactions: number;
  comments: number;
  shares: number;
  subscribers_before: number;
  subscribers_after: number;
  subscribers_delta: number;
  link_clicks: number;
  collected_at: string;
  source: string;
};

export type SecretStatus = {
  provider: "openai" | "anthropic" | "gemini" | "max" | "telegram";
  secret_name: string;
  status: "missing" | "configured" | "verified" | "failed" | "disabled";
  masked_value: string;
  last_test_at?: string | null;
  last_success_at?: string | null;
  last_error: string;
};

export type RadarEntry = {
  type: "source_item" | "topic";
  id: number;
  source_item_id?: number | null;
  topic_id?: number | null;
  title: string;
  url: string;
  source: string;
  source_id?: number | null;
  channel: string;
  detected_at: string;
  published_at?: string | null;
  source_updated_at?: string | null;
  age_minutes: number;
  content_age_minutes: number;
  detection_age_minutes: number;
  is_new_to_system: boolean;
  is_new_in_world: boolean;
  freshness_basis: string;
  content_type: string;
  source_priority: string;
  freshness_score: number;
  importance_score: number;
  urgency_score: number;
  story_cluster_id: string;
  freshness_status: "breaking" | "fresh" | "developing" | "newly_discovered_reference" | "evergreen" | "stale" | "unknown_date";
  freshness_reason: string;
  status: string;
  linked_topic_id?: number | null;
};

export type RadarResponse = {
  windows: number[];
  window_minutes: number;
  items: RadarEntry[];
  topics: RadarEntry[];
  sections?: Record<string, RadarEntry[]>;
};

export type SecretsStatus = {
  storage_ready: boolean;
  storage_error: string;
  providers: SecretStatus[];
};

function endpointUrl(path: string): string {
  return `${API_URL}${path}`;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const url = endpointUrl(path);
  try {
    const response = await fetch(url, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(options?.headers || {})
      },
      cache: "no-store"
    });
    if (!response.ok) {
      const text = await response.text();
      let detail = text || response.statusText;
      try {
        const parsed = JSON.parse(text);
        detail = parsed.detail || parsed.error || text;
      } catch {
        detail = text || response.statusText;
      }
      throw new Error(String(detail));
    }
    if (response.status === 204) {
      return undefined as T;
    }
    return response.json();
  } catch (error: any) {
    const message = error?.message || "Unknown API error";
    throw new Error(`${options?.method || "GET"} ${path} failed: ${message}`);
  }
}

export const api = {
  status: () => request<ApiStatus>("/api/status"),
  settings: () => request<SystemSettings>("/api/settings"),
  updateSettings: (data: Partial<SystemSettings>) =>
    request<SystemSettings>("/api/settings", { method: "PATCH", body: JSON.stringify(data) }),
  startEditorialWorkday: () =>
    request<{ status: string; settings: SystemSettings; reopened_tasks: number; configs_updated: number; publisher_agents_disabled: number; publishing_enabled: boolean }>("/api/system/start-editorial-workday", { method: "POST" }),
  pauseAllAgents: () => request<{ paused: number }>("/api/system/pause-agents", { method: "POST" }),
  pauseAllRoutines: () => request<{ disabled: number }>("/api/system/pause-routines", { method: "POST" }),
  demoData: () => request<{ source_id: number; topic_id: number; post_id: number }>("/api/dev/demo-data", { method: "POST" }),
  clearDemoData: () => request<{ posts: number; topics: number; sources: number }>("/api/dev/demo-data", { method: "DELETE" }),
  dashboard: () => request<Record<string, number>>("/api/dashboard"),
  channels: () => request<Channel[]>("/api/channels"),
  growth: () => request<GrowthDashboard>("/api/growth"),
  bootstrapGrowth: () => request<GrowthDashboard>("/api/growth/bootstrap", { method: "POST" }),
  generateGrowthPack: (campaignId: number, data: { topic?: string; target_url?: string; create_post?: boolean; comments_count?: number } = {}) =>
    request<GrowthPackResult>(`/api/growth/campaigns/${campaignId}/generate-pack`, { method: "POST", body: JSON.stringify(data) }),
  recordSeedingRun: (data: Partial<SeedingRun> & { campaign_id: number }) =>
    request<{ seeding_run: SeedingRun; dashboard: GrowthDashboard }>("/api/growth/seeding-runs", { method: "POST", body: JSON.stringify(data) }),
  styleLint: (data: { channel_id: number; headline: string; body: string; metadata?: Record<string, any> }) =>
    request<StyleLintResult>("/api/editorial/style-lint", { method: "POST", body: JSON.stringify(data) }),
  updateChannel: (id: number, data: Partial<Channel>) =>
    request<Channel>(`/api/channels/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  sources: (filters?: { showArchived?: boolean; showMockDemo?: boolean }) => {
    const params = new URLSearchParams();
    if (filters?.showArchived) params.set("show_archived", "true");
    if (filters?.showMockDemo) params.set("show_mock_demo", "true");
    const suffix = params.toString() ? `?${params.toString()}` : "";
    return request<Source[]>(`/api/sources${suffix}`);
  },
  createSource: (data: Partial<Source> & { channel_ids?: number[] }) =>
    request<Source>("/api/sources", { method: "POST", body: JSON.stringify(data) }),
  updateSource: (id: number, data: Partial<Source>) =>
    request<Source>(`/api/sources/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  healthCheckSource: (id: number) => request<Source>(`/api/sources/${id}/health-check`, { method: "POST" }),
  fetchSource: (id: number, limit = 5) =>
    request<{ source: Source; result: SourceFetchResult }>(`/api/sources/${id}/fetch?limit=${limit}`, { method: "POST" }),
  deleteSource: (id: number) => request<void>(`/api/sources/${id}`, { method: "DELETE" }),
  editions: () => request<DailyEdition[]>("/api/editions"),
  createTodayEditions: () => request<DailyEdition[]>("/api/editions/today", { method: "POST" }),
  editionDetail: (id: number) => request<EditionDetail>(`/api/editions/${id}`),
  updateEditionNotes: (id: number, editor_notes: string) =>
    request<DailyEdition>(`/api/editions/${id}`, { method: "PATCH", body: JSON.stringify({ editor_notes }) }),
  collectEdition: (id: number) => request<{ edition: DailyEdition; sources: Record<string, any>[] }>(`/api/editions/${id}/collect`, { method: "POST" }),
  selectEditionTop: (id: number) => request<{ edition: DailyEdition; selected_topic_ids: number[] }>(`/api/editions/${id}/select-top`, { method: "POST" }),
  selectEditionTopic: (editionId: number, topicId: number) =>
    request<{ topic_id: number; status: string; edition: DailyEdition }>(`/api/editions/${editionId}/topics/${topicId}/select`, { method: "POST" }),
  rejectEditionTopic: (editionId: number, topicId: number) =>
    request<{ topic_id: number; status: string; edition: DailyEdition }>(`/api/editions/${editionId}/topics/${topicId}/reject`, { method: "POST" }),
  generateEditionPost: (editionId: number, topicId: number) =>
    request<{ post_id: number; post_status: string; created?: boolean; message?: string; edition: DailyEdition }>(`/api/editions/${editionId}/topics/${topicId}/generate-post`, { method: "POST" }),
  regenerateEditionPost: (editionId: number, postId: number) =>
    request<{ post_id: number; post_status: string; edition: DailyEdition }>(`/api/editions/${editionId}/posts/${postId}/regenerate`, { method: "POST" }),
  approveEditionPost: (editionId: number, postId: number, human_note = "") =>
    request<{ post_id: number; post_status: string; edition: DailyEdition }>(`/api/editions/${editionId}/posts/${postId}/approve-final`, { method: "POST", body: JSON.stringify({ human_note }) }),
  rejectEditionPost: (editionId: number, postId: number) =>
    request<{ post_id: number; post_status: string; edition: DailyEdition }>(`/api/editions/${editionId}/posts/${postId}/reject`, { method: "POST" }),
  sourceItems: (filters?: { sourceId?: number; status?: string; language?: string; duplicate?: boolean; blocked?: boolean; showArchived?: boolean; showMockDemo?: boolean }) => {
    const params = new URLSearchParams();
    if (filters?.sourceId) params.set("source_id", String(filters.sourceId));
    if (filters?.status) params.set("status", filters.status);
    if (filters?.language) params.set("language", filters.language);
    if (filters?.duplicate !== undefined) params.set("duplicate", String(filters.duplicate));
    if (filters?.blocked !== undefined) params.set("blocked", String(filters.blocked));
    if (filters?.showArchived) params.set("show_archived", "true");
    if (filters?.showMockDemo) params.set("show_mock_demo", "true");
    const suffix = params.toString() ? `?${params.toString()}` : "";
    return request<SourceItem[]>(`/api/source-items${suffix}`);
  },
  createTopicFromSourceItem: (id: number) =>
    request<{ topic_id: number; topic_status: string; source_item: SourceItem }>(`/api/source-items/${id}/create-topic`, { method: "POST" }),
  rejectSourceItem: (id: number) => request<SourceItem>(`/api/source-items/${id}/reject`, { method: "POST" }),
  refetchSourceItem: (id: number) => request<{ result: SourceFetchResult }>(`/api/source-items/${id}/refetch`, { method: "POST" }),
  topics: (filters?: { topicId?: number; channelId?: number; showArchived?: boolean; showMockDemo?: boolean }) => {
    const params = new URLSearchParams();
    if (filters?.topicId) params.set("topic_id", String(filters.topicId));
    if (filters?.channelId) params.set("channel_id", String(filters.channelId));
    if (filters?.showArchived) params.set("show_archived", "true");
    if (filters?.showMockDemo) params.set("show_mock_demo", "true");
    const suffix = params.toString() ? `?${params.toString()}` : "";
    return request<Topic[]>(`/api/topics${suffix}`);
  },
  createTopic: (data: Partial<Topic>) =>
    request<Topic>("/api/topics", { method: "POST", body: JSON.stringify(data) }),
  updateTopic: (id: number, data: Partial<Topic>) =>
    request<Topic>(`/api/topics/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  generateDraft: (id: number, channelId?: number) =>
    request<Post>(`/api/topics/${id}/run-pipeline${channelId ? `?channel_id=${channelId}` : ""}`, { method: "POST" }),
  generateDryRun: (id: number, channelId?: number) =>
    request<Post>(`/api/topics/${id}/run-dry-run${channelId ? `?channel_id=${channelId}` : ""}`, { method: "POST" }),
  requestDryRun: (id: number, channelId?: number) =>
    request<{ status: string; topic_id: number; channel_id?: number | null; message: string }>(`/api/topics/${id}/request-dry-run${channelId ? `?channel_id=${channelId}` : ""}`, { method: "POST" }),
  fastDraft: (id: number, channelId?: number) =>
    request<Post>(`/api/topics/${id}/fast-draft${channelId ? `?channel_id=${channelId}` : ""}`, { method: "POST" }),
  posts: (filters?: { channelId?: number; showArchived?: boolean; showMockDemo?: boolean }) => {
    const params = new URLSearchParams();
    if (filters?.channelId) params.set("channel_id", String(filters.channelId));
    if (filters?.showArchived) params.set("show_archived", "true");
    if (filters?.showMockDemo) params.set("show_mock_demo", "true");
    const suffix = params.toString() ? `?${params.toString()}` : "";
    return request<Post[]>(`/api/posts${suffix}`);
  },
  radar: (windowMinutes = 1440, includeStale = false, channelId?: number) =>
    request<RadarResponse>(`/api/radar?window_minutes=${windowMinutes}&include_stale=${includeStale}${channelId ? `&channel_id=${channelId}` : ""}`),
  radarCreateTopic: (sourceItemId: number) =>
    request<{ topic_id: number; topic: RadarEntry }>(`/api/radar/source-items/${sourceItemId}/create-topic`, { method: "POST" }),
  radarWatchTopic: (topicId: number) =>
    request<RadarEntry>(`/api/radar/topics/${topicId}/watch`, { method: "POST" }),
  radarRejectTopic: (topicId: number) =>
    request<RadarEntry>(`/api/radar/topics/${topicId}/reject`, { method: "POST" }),
  radarFastDraft: (topicId: number, channelId?: number) =>
    request<{ post_id: number; status: string; provider: string; generation_mode: string }>(`/api/radar/topics/${topicId}/fast-draft${channelId ? `?channel_id=${channelId}` : ""}`, { method: "POST" }),
  updatePost: (id: number, data: Partial<Post>) =>
    request<Post>(`/api/posts/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  approvePost: (id: number) => request<Post>(`/api/posts/${id}/approve`, { method: "POST" }),
  qualityCheckPost: (id: number) => request<Post>(`/api/posts/${id}/quality-check`, { method: "POST" }),
  generatePostVisual: (id: number) => request<Post>(`/api/posts/${id}/generate-visual`, { method: "POST" }),
  preparePostMedia: (id: number) => request<Post>(`/api/posts/${id}/prepare-media`, { method: "POST" }),
  prepareMaxPackage: (id: number) => request<Post>(`/api/posts/${id}/prepare-max-package`, { method: "POST" }),
  publishPostToMax: (id: number, note = "") => request<Post>(`/api/posts/${id}/publish-max`, { method: "POST", body: JSON.stringify({ confirm: true, note }) }),
  rejectPost: (id: number) => request<Post>(`/api/posts/${id}/reject`, { method: "POST" }),
  archivePost: (id: number) => request<Post>(`/api/posts/${id}/archive`, { method: "POST" }),
  rewritePost: (id: number, notes: string[] = ["make_more_useful"]) =>
    request<Post>(`/api/posts/${id}/rewrite`, { method: "POST", body: JSON.stringify({ notes }) }),
  schedulePost: (id: number, scheduled_at?: string) =>
    request<Post>(`/api/posts/${id}/schedule`, {
      method: "POST",
      body: JSON.stringify({ scheduled_at: scheduled_at || null })
    }),
  unschedulePost: (id: number) => request<Post>(`/api/posts/${id}/unschedule`, { method: "POST" }),
  tasks: () => request<Task[]>("/api/tasks"),
  orgAgents: () => request<OrgAgent[]>("/api/org/agents"),
  pauseOrgAgent: (id: number) => request<OrgAgent>(`/api/org/agents/${id}/pause`, { method: "POST" }),
  resumeOrgAgent: (id: number) => request<OrgAgent>(`/api/org/agents/${id}/resume`, { method: "POST" }),
  setOrgAgentStatus: (id: number, status: string) =>
    request<OrgAgent>(`/api/org/agents/${id}/status`, { method: "PATCH", body: JSON.stringify({ status }) }),
  goals: () => request<Goal[]>("/api/goals"),
  routines: () => request<Routine[]>("/api/routines"),
  updateRoutine: (id: number, data: Partial<Routine>) =>
    request<Routine>(`/api/routines/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  dryRunRoutine: (id: number) => request<Routine>(`/api/routines/${id}/dry-run`, { method: "POST" }),
  runRoutineOnce: (id: number) => request<Routine>(`/api/routines/${id}/run-once`, { method: "POST" }),
  costs: () => request<CostSummary>("/api/costs/summary"),
  activity: (filters?: { eventType?: string; agentId?: number; entityType?: string }) => {
    const params = new URLSearchParams();
    if (filters?.eventType) params.set("event_type", filters.eventType);
    if (filters?.agentId) params.set("agent_id", String(filters.agentId));
    if (filters?.entityType) params.set("entity_type", filters.entityType);
    const suffix = params.toString() ? `?${params.toString()}` : "";
    return request<ActivityEvent[]>(`/api/activity${suffix}`);
  },
  agentRuns: (filters?: { topicId?: number; postId?: number }) => {
    const params = new URLSearchParams();
    if (filters?.topicId) params.set("topic_id", String(filters.topicId));
    if (filters?.postId) params.set("post_id", String(filters.postId));
    const suffix = params.toString() ? `?${params.toString()}` : "";
    return request<AgentRun[]>(`/api/agent-runs${suffix}`);
  },
  brainStatus: () => request<BrainStatus>("/api/ai-brain/status"),
  brainHealth: () => request<Record<string, any>>("/api/ai-brain/health"),
  brainMigrationPreview: (model = "gemma4:e4b") => request<BrainMigrationPreview>(`/api/ai-brain/migration-preview?model=${encodeURIComponent(model)}`),
  migrateAgentsToLocalGemma: (confirm = false, model = "gemma4:e4b") =>
    request<Record<string, any>>("/api/ai-brain/migrate-local-gemma", { method: "POST", body: JSON.stringify({ confirm, model }) }),
  benchmarkLocalBrain: (quick = false) =>
    request<Record<string, any>>("/api/ai-brain/benchmark-local-brain", { method: "POST", body: JSON.stringify({ quick }) }),
  agentWorkbenchRuns: (filters?: { statusFilter?: string; agent?: string; topicId?: number; postId?: number }) => {
    const params = new URLSearchParams();
    if (filters?.statusFilter) params.set("status_filter", filters.statusFilter);
    if (filters?.agent) params.set("agent", filters.agent);
    if (filters?.topicId) params.set("topic_id", String(filters.topicId));
    if (filters?.postId) params.set("post_id", String(filters.postId));
    const suffix = params.toString() ? `?${params.toString()}` : "";
    return request<AgentRun[]>(`/api/agent-workbench/runs${suffix}`);
  },
  agentWorkbenchRun: (id: number) => request<AgentRun>(`/api/agent-workbench/runs/${id}`),
  agentWorkbenchContracts: () => request<AgentWorkbenchContracts>("/api/agent-workbench/contracts"),
  missionControl: () => request<MissionControlReadModel>("/api/mission-control"),
  missionControlAction: (data: { target_type: string; target_id: number; action: string; note?: string }) =>
    request<Record<string, any>>("/api/mission-control/actions", { method: "POST", body: JSON.stringify(data) }),
  integrations: () => request<Integration[]>("/api/integrations"),
  updateIntegration: (id: number, data: Partial<Integration>) =>
    request<Integration>(`/api/integrations/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  testIntegration: (id: number) => request<{ ok: boolean; error: string; result: Record<string, any>; integration: Integration }>(`/api/integrations/${id}/test`, { method: "POST" }),
  testAdminMessage: (id: number) => request<{ ok: boolean }>(`/api/integrations/${id}/test-admin-message`, { method: "POST" }),
  platformChannels: () => request<PlatformChannel[]>("/api/platform-channels"),
  discoverMaxChats: () => request<{ ok: boolean; chats: MaxDiscoveredChat[]; max_called: boolean; published: boolean }>("/api/platform-channels/max/discover"),
  startMaxChannel: (data: { chat_id: string; title?: string | null; link?: string | null }) =>
    request<StartMaxChannelResult>("/api/platform-channels/max/start", { method: "POST", body: JSON.stringify(data) }),
  updatePlatformChannel: (id: number, data: Partial<PlatformChannel>) =>
    request<PlatformChannel>(`/api/platform-channels/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  testPlatformChannel: (id: number) => request<{ ok: boolean; result?: Record<string, any>; platform_channel: PlatformChannel }>(`/api/platform-channels/${id}/test`, { method: "POST" }),
  channelWorkspace: (id: number) => request<ChannelWorkspace>(`/api/channels/${id}/workspace`),
  attachSourceToChannel: (channelId: number, sourceId: number) =>
    request<{ ok: boolean; action: string; channel_id: number; source: Source }>(`/api/channels/${channelId}/sources/${sourceId}/attach`, { method: "POST" }),
  ingestUrlForChannel: (channelId: number, data: { url: string; title?: string | null }) =>
    request<ChannelUrlIngestResult>(`/api/channels/${channelId}/ingest-url`, { method: "POST", body: JSON.stringify(data) }),
  refreshChannelRadar: (id: number) => request<{ ok: boolean; channel_id: number; sources_scanned: number; totals: Record<string, number>; llm_called: boolean; max_called: boolean; published: boolean }>(`/api/channels/${id}/refresh-radar`, { method: "POST" }),
  secretsStatus: () => request<SecretsStatus>("/api/secrets/status"),
  saveSecret: (provider: string, secretName: string, secretValue: string) =>
    request<SecretStatus>(`/api/secrets/${provider}/${secretName}`, { method: "POST", body: JSON.stringify({ secret_value: secretValue }) }),
  deleteSecret: (provider: string, secretName: string) =>
    request<SecretStatus>(`/api/secrets/${provider}/${secretName}`, { method: "DELETE" }),
  testSecret: (provider: string, secretName: string) =>
    request<{ ok: boolean; error: string; result: Record<string, any>; secret: SecretStatus }>(`/api/secrets/${provider}/${secretName}/test`, { method: "POST" }),
  ownerBotStatus: () => request<{ enabled: boolean; allowed_chat_id: string; has_webhook_secret: boolean; text: string }>("/api/owner-bot/status"),
  updateOwnerBotSettings: (data: { enabled?: boolean; allowed_chat_id?: string }) =>
    request<Record<string, any>>("/api/owner-bot/settings", { method: "PATCH", body: JSON.stringify(data) }),
  pollOwnerBotOnce: () => request<Record<string, any>>("/api/owner-bot/telegram/poll-once", { method: "POST" }),
  sendOwnerBotTest: (text: string) =>
    request<Record<string, any>>("/api/owner-bot/telegram/send-test", { method: "POST", body: JSON.stringify({ text }) }),
  notifications: (status?: string) => request<NotificationItem[]>(`/api/notifications${status ? `?status=${status}` : ""}`),
  unreadNotifications: () => request<{ unread: number }>("/api/notifications/unread-count"),
  markNotificationRead: (id: number) => request<NotificationItem>(`/api/notifications/${id}/read`, { method: "POST" }),
  issues: () => request<Issue[]>("/api/issues"),
  issueDetail: (id: number) => request<IssueDetail>(`/api/issues/${id}/detail`),
  updateIssue: (id: number, data: Partial<Issue>) =>
    request<Issue>(`/api/issues/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  createSubIssue: (id: number, data: Partial<Issue>) =>
    request<Issue>(`/api/issues/${id}/sub-issues`, { method: "POST", body: JSON.stringify(data) }),
  decisionLogs: (filters?: { entityType?: string; entityId?: number; issueId?: number }) => {
    const params = new URLSearchParams();
    if (filters?.entityType) params.set("entity_type", filters.entityType);
    if (filters?.entityId) params.set("entity_id", String(filters.entityId));
    if (filters?.issueId) params.set("issue_id", String(filters.issueId));
    const suffix = params.toString() ? `?${params.toString()}` : "";
    return request<DecisionLog[]>(`/api/decision-logs${suffix}`);
  },
  agentsTelemetry: () => request<AgentTelemetry[]>("/api/agents/telemetry"),
  agentDetail: (id: number) => request<AgentDetail>(`/api/agents/${id}/detail`),
  llmModels: () => request<LLMModel[]>("/api/llm-models"),
  agentConfigs: () => request<AgentConfig[]>("/api/agent-configs"),
  updateAgentConfig: (id: number, data: Partial<AgentConfig>) =>
    request<AgentConfig>(`/api/agent-configs/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  agentRoleFilesPreview: () => request<AgentRoleFilePreview>("/api/agent-configs/role-files/preview"),
  applyAgentRoleFiles: (confirm = true) =>
    request<{ ok: boolean; version: number; applied: Record<string, any>[]; preview: AgentRoleFilePreview }>(
      "/api/agent-configs/role-files/apply",
      { method: "POST", body: JSON.stringify({ confirm }) }
    ),
  configureContentAgentsOpenAI: (model?: string) =>
    request<{ ok: boolean; provider: string; model: string; affected: Record<string, any>[]; runtime_agents: string[]; publisher_disabled: boolean }>(
      "/api/agent-configs/content-agents/openai",
      { method: "POST", body: JSON.stringify({ model: model || null }) }
    ),
  testAgentConfig: (id: number) => request<{ ok: boolean; error: string; result: Record<string, any> }>(`/api/agent-configs/${id}/test`, { method: "POST" }),
  promptTemplates: () => request<PromptTemplate[]>("/api/prompt-templates"),
  createPromptTemplate: (data: Partial<PromptTemplate>) =>
    request<PromptTemplate>("/api/prompt-templates", { method: "POST", body: JSON.stringify(data) }),
  updatePromptTemplate: (id: number, data: Partial<PromptTemplate>) =>
    request<PromptTemplate>(`/api/prompt-templates/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  explain: (entityType: string, entityId: number) => request<ExplainResult>(`/api/explain/${entityType}/${entityId}`),
  buttonContracts: () => request<ButtonContract[]>("/api/ui/button-contracts"),
  runOperatingLoop: (action: OperatingLoopRun["action"], mode: OperatingLoopRun["mode"] = "manual_run") =>
    request<OperatingLoopRun>("/api/operating-loop/run", { method: "POST", body: JSON.stringify({ action, mode }) }),
  latestOperatingLoop: () => request<OperatingLoopRun | null>("/api/operating-loop/latest"),
  runAgencyCheck: () => request<AgencyOperatingReport>("/api/agency/check", { method: "POST" }),
  runMediaDirectorLoop: () => request<MediaDirectorLoopResult>("/api/agency/media-director-loop", { method: "POST" }),
  ensureManagingAgents: () => request<Record<string, any>>("/api/agency/ensure-managing-agents", { method: "POST" }),
  runIssueNextSafeStep: (id: number) =>
    request<{ issue_id: number; status: string; result_summary: string; llm_calls: number; max_called: boolean }>(`/api/agency/issues/${id}/run-next-safe-step`, { method: "POST" }),
  directorSessions: () => request<EditorialDirectorSession[]>("/api/editorial-director/sessions"),
  createDirectorSession: (command: string, mode = "operator_command") =>
    request<EditorialDirectorSession>("/api/editorial-director/sessions", { method: "POST", body: JSON.stringify({ command, mode }) }),
  directorSession: (id: number) => request<EditorialDirectorSession>(`/api/editorial-director/sessions/${id}`),
  sendDirectorMessage: (id: number, content: string) =>
    request<EditorialDirectorSession>(`/api/editorial-director/sessions/${id}/message`, { method: "POST", body: JSON.stringify({ content }) }),
  runMorningBriefing: () => request<EditorialDirectorSession>("/api/editorial-director/morning-briefing", { method: "POST" }),
  runDirectorSourceScan: (data: { max_sources?: number; limit_per_source?: number } = {}) =>
    request<EditorialDirectorSession>("/api/editorial-director/source-scan", { method: "POST", body: JSON.stringify(data) }),
  runJournalistBriefing: (data: { max_items?: number; target_topics?: number } = {}) =>
    request<EditorialDirectorSession>("/api/editorial-director/journalist-briefing", { method: "POST", body: JSON.stringify(data) }),
  editorDayToday: () => request<EditorDayToday>("/api/editor-day/today"),
  editorDayMorningScan: (data: { max_sources?: number; limit_per_source?: number } = {}) =>
    request<EditorialDirectorSession>("/api/editor-day/run-morning-scan", { method: "POST", body: JSON.stringify(data) }),
  editorDayBuildAgenda: (data: { max_items?: number; target_topics?: number } = {}) =>
    request<EditorialDirectorSession>("/api/editor-day/build-agenda", { method: "POST", body: JSON.stringify(data) }),
  editorDayRunFtLive: (data: { max_posts?: number } = {}) =>
    request<EditorialDirectorSession>("/api/editor-day/run-ft-live", { method: "POST", body: JSON.stringify(data) }),
  submissions: (status?: string) => request<NewsroomSubmission[]>(`/api/submissions${status ? `?status=${status}` : ""}`),
  createSubmissionTopic: (id: number) => request<Topic>(`/api/submissions/${id}/create-topic`, { method: "POST" }),
  rejectSubmission: (id: number, reason = "") => request<Record<string, any>>(`/api/submissions/${id}/reject`, { method: "POST", body: JSON.stringify({ reason }) }),
  launchReadiness: () => request<LaunchReadiness>("/api/launch/readiness"),
  launchCleanupGenerated: (data: { mode: "archive_only" | "archive_and_delete"; include_mock: boolean; include_dry_run: boolean; include_final_packs: boolean; confirm: boolean }) =>
    request<Record<string, any>>("/api/launch/cleanup-generated-content", { method: "POST", body: JSON.stringify(data) }),
  runLaunchTextCycle: (data: { channels: string[]; max_posts: number; mode: "production_manual" }) =>
    request<Record<string, any>>("/api/launch/run-text-cycle", { method: "POST", body: JSON.stringify(data) }),
  relays: () => request<RelayChannel[]>("/api/relays"),
  createRelay: (data: { name: string; slug?: string; max_chat_id?: string; max_url?: string; source_urls: string[]; max_posts_per_day?: number; check_interval_minutes?: number; auto_publish_low_risk?: boolean }) =>
    request<RelayChannel>("/api/relays", { method: "POST", body: JSON.stringify(data) }),
  runRelay: (id: number, maxPosts?: number) =>
    request<Record<string, any>>(`/api/relays/${id}/run${maxPosts ? `?max_posts=${maxPosts}` : ""}`, { method: "POST" }),
  markPostPublishedManually: (id: number, data: { channel?: string; published_at?: string | null; published_url?: string; note?: string }) =>
    request<Post>(`/api/posts/${id}/mark-published-manually`, { method: "POST", body: JSON.stringify(data) }),
  postMetrics: () => request<PostMetric[]>("/api/metrics/posts"),
  recordPostMetrics: (postId: number, data: Partial<PostMetric>) =>
    request<PostMetric>(`/api/metrics/posts/${postId}`, { method: "POST", body: JSON.stringify(data) })
};
