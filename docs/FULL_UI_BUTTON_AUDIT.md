# Full UI Button Audit

Audit target: `http://194.87.243.63:13000/`

Method:
- Browser inventory across 17 frontend routes.
- Expanded Playwright smoke against public UI.
- API/state validation for state-changing actions.
- Console and network monitoring, ignoring expected SSE aborts on navigation.

## Summary

| Metric | Count |
| --- | ---: |
| Pages inspected | 17 |
| Visible controls found | 1651 |
| Visible buttons found | 868 |
| Disabled controls with visible/title reason | 181 |
| Console errors after fixes | 0 |
| Unexpected network 422/500 after fixes | 0 |
| Known clickable no-op buttons remaining | 0 |

## Page Inventory

| Route | Purpose | Controls | Buttons | Disabled | Status | Fixed during audit |
| --- | --- | ---: | ---: | ---: | --- | --- |
| `/` | Operator dashboard and readiness | 42 | 6 | 2 | WORKING | Readiness/CTA smoke verified |
| `/channels` | Channel rules and MAX-safe channel binding | 49 | 9 | 1 | WORKING | Reworked from long raw form, added toast, safe MAX disabled action |
| `/sources` | Source registry and source-channel mapping | 69 | 10 | 1 | WORKING | Added validation, toast, safe delete confirm, source health feedback |
| `/topics` | Topic creation and draft/dry-run actions | 251 | 223 | 37 | WORKING | Dry-run smoke verified |
| `/posts` | Review queue | 320 | 214 | 56 | WORKING | Save/copy/disabled publish reasons smoke verified |
| `/calendar` | Scheduled posts | 23 | 0 | 0 | DISABLED_CORRECTLY | Empty state clarified; no scheduled publish controls visible |
| `/integrations` | Secrets, model selection, provider tests | 50 | 13 | 10 | WORKING | OpenAI apply/test readiness smoke verified |
| `/notifications` | Human/action notifications | 198 | 80 | 48 | WORKING | Added archive disabled reason and toast for read action |
| `/issues` | Operational Kanban | 212 | 190 | 0 | WORKING | Detail open, legal transition and illegal 422 smoke verified |
| `/org` | Agent hierarchy and authority | 44 | 21 | 0 | WORKING | Added toast/error handling and Publisher explanation |
| `/goals` | CEO loop goals | 33 | 11 | 11 | DISABLED_CORRECTLY | Read-only actions disabled with reason |
| `/routines` | Autonomous routine controls | 57 | 15 | 5 | WORKING | Run-once blocked with reason, dry-run smoke verified |
| `/costs` | Cost/budget visibility | 23 | 0 | 0 | WORKING | Copy clarified; links to logs |
| `/activity` | Activity ledger | 99 | 1 | 0 | WORKING | Filters smoke verified; copy clarified |
| `/agents` | Agent control center | 99 | 58 | 2 | WORKING | Config drawer save smoke verified |
| `/prompts` | Prompt templates/versioning | 58 | 17 | 8 | WORKING | Create/save toast and rollback disabled reason |
| `/logs` | Tasks and agent runs | 24 | 0 | 0 | WORKING | Filtering added, copy clarified |

## Critical Controls Exercised End-to-End

| Page | Control | Endpoint/state | Result |
| --- | --- | --- | --- |
| Dashboard | Readiness/Integrations link | navigation | WORKING |
| Integrations | Apply OpenAI to content agents | `POST /api/agent-configs/content-agents/openai` | WORKING, activity event |
| Agents | Open config drawer | UI drawer | WORKING |
| Agents | Save config | `PATCH /api/agent-configs/{id}` | WORKING, persisted |
| Channels | Save rules | `PATCH /api/channels/{id}` | WORKING, activity event |
| Channels | Test MAX link | `POST /api/platform-channels/{id}/test` | WORKING, no publish |
| Sources | Add source | `POST /api/sources` | WORKING, activity event |
| Sources | Health check | `POST /api/sources/{id}/health-check` | WORKING, activity event |
| Topics | Run real dry-run | `POST /api/topics/{id}/run-dry-run` | WORKING, dry_run post |
| Posts | Save edits | `PATCH /api/posts/{id}` | WORKING, activity event |
| Posts | Copy text | browser clipboard/client feedback | WORKING |
| Issues | Open issue detail | `GET /api/issues/{id}/detail` | WORKING |
| Issues | Valid transition | `PATCH /api/issues/{id}` | WORKING, activity event |
| Issues | Illegal transition | `PATCH /api/issues/{id}` | 422 with clear state-machine block |
| Notifications | Mark read | `POST /api/notifications/{id}/read` | WORKING, badge updates |
| Routines | Dry run | `POST /api/routines/{id}/dry-run` | WORKING, no external publish |
| Prompts | Save prompt | `PATCH /api/prompt-templates/{id}` | WORKING, activity event |
| Activity | Apply filters | `GET /api/activity` | WORKING |
| Logs | Open logs | `GET /api/tasks`, `GET /api/agent-runs` | WORKING |

## Disabled Correctly

- MAX public publish: disabled because Step 2.7 excludes public publishing.
- Publisher Agent: disabled until MAX publishing step.
- Provider test buttons: disabled in mock mode for real LLM safety.
- Dry-run actions: disabled unless system mode, provider key, agents, source URL and budget are ready.
- Mock/dry-run post schedule/approve: disabled because posts are not public-publishable.
- Goals create/update/status: disabled because backend goal mutation endpoints are not implemented yet.
- Notification archive: disabled because archive endpoint is not implemented yet.
- Prompt rollback: disabled with explanation; manual active-version selection remains available.
- Routine run once: disabled while global routines are off.

## Remaining UX Debt

- Channels still need richer tabbed subviews for rules/sources/statistics.
- Issues lacks explicit mode tabs for operational/agent/channel view; current Kanban is operational only.
- Goals are read-only; mutation endpoints are future work.
- Calendar has no scheduled posts in safe Step 2.7 state, so reschedule controls are only available if a scheduled post exists.
- Some data values remain technical in details/logs by design.
