# ERA Media Factory UI Audit

Audit date: 2026-04-30

Scope: Step 2.6 control plane after deployment. This audit does not start Step 2.7, does not enable MAX publishing, does not enable real LLM calls, and does not enable autonomous routines.

## System Availability

| Check | Result | Notes |
|---|---:|---|
| `docker compose ps` | Working | Backend, frontend, Postgres, Redis, worker, scheduler were running on the server during audit. |
| Backend health | Working | `http://194.87.243.63:18000/health` returned `{"status":"ok"}`. |
| DB health | Working | Postgres accepted connections; `/api/status` reported `database_ok=true`. |
| Frontend health | Working | `http://194.87.243.63:13000/` returned HTTP 200. |
| Migrations status | Working | Alembic current revision: `0007_operating_loop_kanban (head)`. |
| Seed status | Working | 5 channels and 19 org agents were present. |
| Public frontend URL | Working | Port `13000` is published by Docker and allowed in UFW. |
| Public backend URL | Working | Port `18000` is published and `/health` is reachable. |

## Page Inventory

| Page | Route | Purpose | API endpoints used | Data loaded | Empty state | Buttons present | Broken buttons | Notes | Must fix |
|---|---|---|---|---:|---:|---|---|---|---|
| Панель | `/` | Status, safety switches, CEO loop | `/api/status`, `/api/dashboard`, `/api/settings`, `/api/operating-loop/latest`, `/api/operating-loop/run`, `/api/dev/demo-data`, `/api/system/pause-*` | yes | yes | create/clear demo, safety toggles, pause all, CEO loop | none found | Settings save immediately; some statuses are technical. | Add clearer saved feedback for settings. |
| Каналы | `/channels` | Editorial channel config and MAX mapping | `/api/channels`, `/api/platform-channels` | yes | partial | save channel, save MAX, test connection, publish/status selects | none found | Publish modes are technical; `auto` is safety-limited backend-side. | Add Russian explanations for publish modes. |
| Источники | `/sources` | Source registry and channel assignment | `/api/sources`, `/api/channels` | yes | partial | add, save, health, delete, channel assignment, trust/status | fixed | Delete now writes activity. `Health` label remains English. | Add delete confirmation and translate Health. |
| Темы | `/topics` | Topics and safe manual pipeline | `/api/topics`, `/api/channels`, `/api/agent-runs`, `/api/decision-logs`, `/api/explain` | yes | partial | create, draft, review, logs, explain, reject | none found | Draft button creates issue/task/post/logs in mock. | Add clearer mock-only notice near draft action. |
| Посты | `/posts` | Review queue and post editing | `/api/posts`, `/api/channels`, `/api/decision-logs`, `/api/explain` | yes | partial | save, approve, schedule, rewrite, explain, copy, reject, archive | fixed | Mock badge is visible; approve/schedule disabled for mock. Copy now gives feedback. | Translate remaining technical labels. |
| Календарь | `/calendar` | Scheduled posts | `/api/posts`, `/api/channels`, `/api/posts/{id}/schedule`, `/unschedule` | yes | yes | reschedule, unschedule | none found | Empty in mock unless approved scheduled posts exist. | Add open post link later. |
| Интеграции | `/integrations` | MAX, LLM, admin integrations | `/api/integrations`, `/api/integrations/{id}/test`, `/test-admin-message` | yes | partial | save, test, admin test, copy env | fixed | MAX token is masked; base URL shown; copy label translated. | Keep public publish disabled. |
| Уведомления | `/notifications` | Warning/review/failure center | `/api/notifications`, `/api/notifications/unread-count`, `/api/notifications/{id}/read` | yes | partial | mark as read, open related page | archive absent | Severity/status are technical. | Add archive only if it becomes real. |
| Задачи | `/issues` | Agent Kanban and issue detail | `/api/issues`, `/api/issues/{id}/detail`, `/api/issues/{id}/sub-issues`, `/api/decision-logs` | yes | partial | open, transitions, save, sub-issue, waiting human, complete, cancel | fixed | Manual transitions now create decision logs; illegal transitions log rejection. | Show 422 errors more clearly in UI. |
| Оргструктура | `/org` | Agent hierarchy and status control | `/api/org/agents`, `/api/org/agents/{id}/status` | yes | yes | select, refresh, pause/resume/status | none found | Publisher cannot resume; backend blocks it. | Add link to agent detail. |
| Цели | `/goals` | Operational goals | `/api/goals`, `/api/org/agents` | yes | partial | none | none | Read-only page; edit/create requested actions are not visible. | Add real CRUD later if needed. |
| Регламенты | `/routines` | Routine config and guarded manual run | `/api/routines`, `/api/org/agents`, `/api/routines/{id}` | yes | partial | save, dry run, run once, enable checkbox | none found | Run once is safely blocked while global routines are disabled. | Better blocked feedback. |
| Расходы | `/costs` | Cost summary | `/api/costs/summary` | yes | yes | none | none | Mock costs are near zero. | No urgent fix. |
| Активность | `/activity` | Activity feed and filters | `/api/activity`, `/api/org/agents`, SSE | yes | partial | apply filters, entity links | none found | Event names are technical. | Translate common event types. |
| Агенты | `/agents` | Agent telemetry and quick config | `/api/agents/telemetry`, `/api/org/agents`, `/api/agent-configs`, `/api/llm-models` | yes | partial | pause/resume, config, quick save, test prompt | none found | Test is mock in mock mode. | Add mode badge near test button. |
| Agent detail | `/agents/{id}` | Full agent config, runs, issues, decisions | `/api/agents/{id}/detail`, `/api/agent-configs`, `/api/llm-models`, `/api/prompt-templates` | yes | partial | back, pause/resume, save config, test agent | none found | Technical field names acceptable in detail. | Add dry/live provider key hints before Step 2.7. |
| Промпты | `/prompts` | Prompt templates and versions | `/api/prompt-templates`, `/api/org/agents` | yes | partial | save/status | none found | Create/rollback not visible, not implemented. | Add later if required. |
| Логи | `/logs` | Tasks and agent runs | `/api/tasks`, `/api/agent-runs` | yes | partial | none | none | Read-only; filters/refresh requested but not implemented. | Add filters/refresh later. |

## Button Classification

| Area | Buttons | State |
|---|---|---|
| Dashboard | Create demo, clear demo, safety toggles, pause agents/routines, create daily plan, refresh Kanban, check blockers | Working end-to-end. |
| Channels | Save channel, save MAX, test connection, publish/status changes | Working; activity events are created. |
| Sources | Add, save, health check, delete, assign channels, trust/status changes | Working; delete activity was fixed. |
| Topics | Create topic, draft pipeline, review, logs, explain, reject | Working. |
| Posts | Save, approve, reject, rewrite, schedule, copy, explain, archive mock | Working; mock approve/schedule disabled and backend-blocked. |
| Calendar | Reschedule, unschedule | Working for scheduled posts. |
| Integrations | Save, test, admin test, copy env | Working; MAX token is not exposed. |
| Notifications | Mark read, open related page | Working; archive is not visible. |
| Issues | Open, valid transition, illegal transition, complete, cancel, decisions, sub-issues | Working; illegal transition returns 422 and logs activity. |
| Org / Agents | Pause/resume, config, save config, test agent | Working; Publisher resume is backend-blocked. |
| Prompts | Save/status | Working; content changes create new version. |
| Routines | Enable/disable draft, save, dry run, run once | Working; autonomous run remains globally blocked. |
| Goals | No visible edit buttons | Read-only, not broken. |
| Logs | No visible action buttons | Read-only, not broken. |

## Known Limitations

- Browser automation in the current Codex Windows environment is unstable (`spawn EPERM` or `networkidle` timeout). `tools/smoke_ui.mjs` now falls back to strict API-backed UI smoke checks, and that fallback passes.
- Some user-facing labels remain technical or English.
- Dashboard separates mock/not-publishable post counts, but true dry_run/live post split still needs explicit generation-mode metadata in Step 2.7.
