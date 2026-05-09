export const API_URL = "";

export type ApiStatus = {
  status: string;
  service: string;
  database_ok: boolean;
  active_channels: number;
  dev_mode: boolean;
  system_mode: "mock" | "dry_run" | "live";
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
  status: string;
};

export type Source = {
  id: number;
  name: string;
  url: string;
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
  channel_ids: number[];
  items_count?: number;
  valid_items_count?: number;
  duplicate_items_count?: number;
  failed_items_count?: number;
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
  relevance_score?: number;
  content_length?: number;
  extraction_status?: string;
  extraction_error?: string;
  language?: string;
  source_published_at?: string | null;
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
  detected_at: string;
  language: string;
  content_length: number;
  extraction_status: string;
  extraction_error: string;
  paywall_or_blocked_detected: boolean;
  duplicate_of_item_id?: number | null;
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
  status: string;
  risk_score: number;
  quality_score: number;
  status_reason: string;
  risk_reason: string;
  quality_reason: string;
  scheduled_at?: string | null;
  version: number;
  version_history: Record<string, any>[];
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
  system_mode: "mock" | "dry_run" | "live";
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

export type SecretStatus = {
  provider: "openai" | "anthropic" | "gemini" | "max";
  secret_name: string;
  status: "missing" | "configured" | "failed" | "disabled";
  masked_value: string;
  last_test_at?: string | null;
  last_success_at?: string | null;
  last_error: string;
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
  pauseAllAgents: () => request<{ paused: number }>("/api/system/pause-agents", { method: "POST" }),
  pauseAllRoutines: () => request<{ disabled: number }>("/api/system/pause-routines", { method: "POST" }),
  demoData: () => request<{ source_id: number; topic_id: number; post_id: number }>("/api/dev/demo-data", { method: "POST" }),
  clearDemoData: () => request<{ posts: number; topics: number; sources: number }>("/api/dev/demo-data", { method: "DELETE" }),
  dashboard: () => request<Record<string, number>>("/api/dashboard"),
  channels: () => request<Channel[]>("/api/channels"),
  updateChannel: (id: number, data: Partial<Channel>) =>
    request<Channel>(`/api/channels/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  sources: () => request<Source[]>("/api/sources"),
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
    request<{ post_id: number; post_status: string; edition: DailyEdition }>(`/api/editions/${editionId}/topics/${topicId}/generate-post`, { method: "POST" }),
  regenerateEditionPost: (editionId: number, postId: number) =>
    request<{ post_id: number; post_status: string; edition: DailyEdition }>(`/api/editions/${editionId}/posts/${postId}/regenerate`, { method: "POST" }),
  approveEditionPost: (editionId: number, postId: number, human_note = "") =>
    request<{ post_id: number; post_status: string; edition: DailyEdition }>(`/api/editions/${editionId}/posts/${postId}/approve-final`, { method: "POST", body: JSON.stringify({ human_note }) }),
  rejectEditionPost: (editionId: number, postId: number) =>
    request<{ post_id: number; post_status: string; edition: DailyEdition }>(`/api/editions/${editionId}/posts/${postId}/reject`, { method: "POST" }),
  sourceItems: (filters?: { sourceId?: number; status?: string; language?: string; duplicate?: boolean; blocked?: boolean }) => {
    const params = new URLSearchParams();
    if (filters?.sourceId) params.set("source_id", String(filters.sourceId));
    if (filters?.status) params.set("status", filters.status);
    if (filters?.language) params.set("language", filters.language);
    if (filters?.duplicate !== undefined) params.set("duplicate", String(filters.duplicate));
    if (filters?.blocked !== undefined) params.set("blocked", String(filters.blocked));
    const suffix = params.toString() ? `?${params.toString()}` : "";
    return request<SourceItem[]>(`/api/source-items${suffix}`);
  },
  createTopicFromSourceItem: (id: number) =>
    request<{ topic_id: number; topic_status: string; source_item: SourceItem }>(`/api/source-items/${id}/create-topic`, { method: "POST" }),
  rejectSourceItem: (id: number) => request<SourceItem>(`/api/source-items/${id}/reject`, { method: "POST" }),
  refetchSourceItem: (id: number) => request<{ result: SourceFetchResult }>(`/api/source-items/${id}/refetch`, { method: "POST" }),
  topics: () => request<Topic[]>("/api/topics"),
  createTopic: (data: Partial<Topic>) =>
    request<Topic>("/api/topics", { method: "POST", body: JSON.stringify(data) }),
  updateTopic: (id: number, data: Partial<Topic>) =>
    request<Topic>(`/api/topics/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  generateDraft: (id: number, channelId?: number) =>
    request<Post>(`/api/topics/${id}/run-pipeline${channelId ? `?channel_id=${channelId}` : ""}`, { method: "POST" }),
  generateDryRun: (id: number, channelId?: number) =>
    request<Post>(`/api/topics/${id}/run-dry-run${channelId ? `?channel_id=${channelId}` : ""}`, { method: "POST" }),
  posts: () => request<Post[]>("/api/posts"),
  updatePost: (id: number, data: Partial<Post>) =>
    request<Post>(`/api/posts/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  approvePost: (id: number) => request<Post>(`/api/posts/${id}/approve`, { method: "POST" }),
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
  integrations: () => request<Integration[]>("/api/integrations"),
  updateIntegration: (id: number, data: Partial<Integration>) =>
    request<Integration>(`/api/integrations/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  testIntegration: (id: number) => request<{ ok: boolean; error: string; result: Record<string, any>; integration: Integration }>(`/api/integrations/${id}/test`, { method: "POST" }),
  testAdminMessage: (id: number) => request<{ ok: boolean }>(`/api/integrations/${id}/test-admin-message`, { method: "POST" }),
  platformChannels: () => request<PlatformChannel[]>("/api/platform-channels"),
  updatePlatformChannel: (id: number, data: Partial<PlatformChannel>) =>
    request<PlatformChannel>(`/api/platform-channels/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  testPlatformChannel: (id: number) => request<{ ok: boolean; platform_channel: PlatformChannel }>(`/api/platform-channels/${id}/test`, { method: "POST" }),
  secretsStatus: () => request<SecretsStatus>("/api/secrets/status"),
  saveSecret: (provider: string, secretName: string, secretValue: string) =>
    request<SecretStatus>(`/api/secrets/${provider}/${secretName}`, { method: "POST", body: JSON.stringify({ secret_value: secretValue }) }),
  deleteSecret: (provider: string, secretName: string) =>
    request<SecretStatus>(`/api/secrets/${provider}/${secretName}`, { method: "DELETE" }),
  testSecret: (provider: string, secretName: string) =>
    request<{ ok: boolean; error: string; result: Record<string, any>; secret: SecretStatus }>(`/api/secrets/${provider}/${secretName}/test`, { method: "POST" }),
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
  latestOperatingLoop: () => request<OperatingLoopRun | null>("/api/operating-loop/latest")
};
