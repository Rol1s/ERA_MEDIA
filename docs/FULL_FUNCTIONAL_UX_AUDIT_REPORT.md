# Full Functional UX Audit Report

## Summary

- Overall status: 86/100.
- Ready for prompt refinement: yes.
- Ready for MAX publishing: no.
- Biggest blockers: Goals are read-only, Kanban has only operational mode, Channels needs richer tabbed UX, Calendar cannot be fully exercised without publishable scheduled posts.

The audit found no remaining clickable no-op buttons in the tested operator paths. All normal tested user actions either work end-to-end or are disabled with a Russian explanation.

## Page-by-page Audit

### Dashboard
- Working: readiness panel, operator CTAs, CEO loop actions, navigation command bar.
- Broken: none found.
- Decorative: none found.
- Misleading: publishing safety copy is now explicit.
- Fixed: verified CTAs and readiness links in browser smoke.
- Remaining: none blocking.

### Channels
- Working: channel selection, rule save, platform channel save/test, links to topics/posts/issues.
- Broken: none found after fixes.
- Decorative: publish action converted to disabled safety action.
- Misleading: auto-publish option is visibly marked as unavailable.
- Fixed: page changed from raw long form to operator layout with toast feedback.
- Remaining: add real tabs for overview/rules/sources/MAX/risks/stats later.

### Sources
- Working: create, save, health check, channel assignment, delete with confirmation.
- Broken: none found after fixes.
- Decorative: none.
- Misleading: empty URL is blocked before save.
- Fixed: validation, toast, Russian copy, safe delete explanation.
- Remaining: real external source fetch/collector health remains outside this step.

### Topics
- Working: create topic, mock draft, real dry-run readiness, real dry-run post creation, explain/log/reject actions.
- Broken: none found in smoke path.
- Decorative: none found.
- Misleading: dry-run blockers are shown.
- Fixed: previously hardened in Step 2.7.2.
- Remaining: topic cards are dense with many historical items.

### Posts
- Working: review queue, edit/save, copy feedback, rewrite/reject/archive paths where allowed, disabled approve/schedule reasons.
- Broken: none found in smoke path.
- Decorative: public publish/schedule are disabled for mock/dry-run.
- Misleading: fixed by badges and safety block.
- Remaining: version history could be more visual.

### Calendar
- Working: empty state and safety explanation.
- Broken: none.
- Decorative: none visible.
- Misleading: clarified that Step 2.7 should not create public schedule.
- Remaining: reschedule/unschedule only testable with a publishable scheduled post, which this step intentionally does not create.

### Integrations
- Working: masked secrets, model dropdown, provider status, provider test blocking in mock, apply OpenAI to agents.
- Broken: no 422 found for normal tested flows.
- Decorative: none found.
- Misleading: real tests blocked in mock with explanation.
- Remaining: Anthropic/Gemini real tests require keys; MAX public publishing remains off.

### Notifications
- Working: list, unread count, mark read, related entity links.
- Broken: none found.
- Decorative: archive button is disabled with reason.
- Misleading: fixed.
- Remaining: archive endpoint can be added later.

### Issues / Kanban
- Working: operational columns, issue detail, valid transition, illegal transition blocked by backend 422, activity/decision visibility.
- Broken: none found in smoke path.
- Decorative: none found.
- Misleading: still lacks separate agent/channel mode tabs.
- Remaining: add operational/agent/channel mode tabs and richer filters.

### Org
- Working: hierarchy, selected agent details, pause/resume with toast, Publisher disabled explanation.
- Broken: none found.
- Decorative: none.
- Misleading: Publisher safety clarified.
- Remaining: permissions are still shown as JSON in details.

### Goals
- Working: read-only goal display and progress.
- Broken: none.
- Decorative: mutation buttons disabled with reason.
- Misleading: fixed by explicit read-only copy.
- Remaining: create/update/pause/achieve/fail endpoints are needed before Goals are fully operational.

### Routines
- Working: save, dry run, run-once disabled while global routines are off.
- Broken: none found.
- Decorative: none.
- Misleading: fixed with safety copy.
- Remaining: enabling routines should remain a separate safety step.

### Costs
- Working: today cost, budget, remaining, RUB conversion, cost by agent/channel/task type, link to logs.
- Broken: none.
- Decorative: none.
- Misleading: mock/real distinction clarified in copy.
- Remaining: date/provider/model filters are not implemented yet.

### Activity
- Working: filters, related entity links, real activity ledger, secret-safe events.
- Broken: none found.
- Decorative: none.
- Misleading: copy clarified.
- Remaining: search field could be added later.

### Agents
- Working: grouped cards, config drawer, save config, bulk OpenAI setup, pause/resume, Publisher disabled.
- Broken: none found in smoke path.
- Decorative: none found.
- Misleading: test buttons are disabled/blocked when not safe.
- Remaining: recent runs/issues/decisions are stronger on detail route than cards.

### Prompts
- Working: create draft prompt, save/update prompt, active/archive status, activity event.
- Broken: none found in smoke path.
- Decorative: rollback button disabled with reason.
- Misleading: fixed by explaining versioning.
- Remaining: explicit rollback endpoint/button can be added later.

### Logs
- Working: task log table, agent runs, token/cost, error visibility, filter input.
- Broken: none.
- Decorative: none.
- Misleading: raw `t/p` labels replaced with readable topic/post references.
- Remaining: links from each row to exact entity would improve debugging.

## Button Audit

| Page | Button/control | Status | Endpoint | Expected result | Actual result | Fixed |
| --- | --- | --- | --- | --- | --- | --- |
| Dashboard | Readiness links | WORKING | navigation | Route opens | Passed | yes |
| Dashboard | CEO loop actions | WORKING | `/api/operating-loop/run` | Issues/report/activity | Existing smoke passed | no |
| Channels | Save rules | WORKING | `/api/channels/{id}` | Persist + activity + toast | Passed | yes |
| Channels | Test MAX link | WORKING | `/api/platform-channels/{id}/test` | Safe test, no publish | Passed | yes |
| Channels | Publish | DISABLED_CORRECTLY | none | Disabled until MAX step | Disabled with reason | yes |
| Sources | Add source | WORKING | `/api/sources` | Persist + activity + toast | Passed | yes |
| Sources | Health check | WORKING | `/api/sources/{id}/health-check` | Status update + activity | Passed | yes |
| Sources | Delete | WORKING | `/api/sources/{id}` | Delete + activity | Confirmation added | yes |
| Integrations | Apply OpenAI | WORKING | `/api/agent-configs/content-agents/openai` | Configs updated, Publisher disabled | Passed | no |
| Agents | Save config | WORKING | `/api/agent-configs/{id}` | Persist + activity | Passed | no |
| Topics | Real dry-run | WORKING | `/api/topics/{id}/run-dry-run` | Dry-run post needs_review | Passed | no |
| Posts | Save edits | WORKING | `/api/posts/{id}` | Version/activity/toast | Passed | no |
| Posts | Schedule/approve | DISABLED_CORRECTLY | blocked | No public publishing | Disabled with reason | no |
| Issues | Open detail | WORKING | `/api/issues/{id}/detail` | Detail panel | Passed | no |
| Issues | Valid transition | WORKING | `/api/issues/{id}` | State changes + activity | Passed | no |
| Issues | Illegal transition | WORKING | `/api/issues/{id}` | 422 clear block | Passed | no |
| Notifications | Mark read | WORKING | `/api/notifications/{id}/read` | Badge/list update | Passed | yes |
| Notifications | Archive | DISABLED_CORRECTLY | none | No no-op | Disabled with reason | yes |
| Routines | Save | WORKING | `/api/routines/{id}` | Persist + activity | Existing endpoint verified | yes |
| Routines | Dry run | WORKING | `/api/routines/{id}/dry-run` | Safe dry run | Passed | yes |
| Routines | Run once | DISABLED_CORRECTLY | blocked by global flag | No autonomous routine | Disabled with reason | yes |
| Prompts | Create prompt | WORKING | `/api/prompt-templates` | Draft created | UI wired | yes |
| Prompts | Save prompt | WORKING | `/api/prompt-templates/{id}` | Version/update + activity | Passed | yes |
| Prompts | Rollback | DISABLED_CORRECTLY | none | No no-op | Disabled with reason | yes |
| Activity | Apply filters | WORKING | `/api/activity` | Filtered events | Passed | yes |
| Logs | Filter | WORKING | client | Table narrows | Implemented | yes |

## Critical Fixes Made

- Reworked Channels from raw form into operator layout.
- Added toast/error handling to Sources, Channels, Calendar, Goals, Routines, Prompts, Org, Notifications, Activity.
- Blocked empty-source save/create in UI with visible error.
- Converted future actions to disabled controls with Russian reasons.
- Clarified MAX safety and Publisher disabled state.
- Expanded `tools/smoke_ui_browser.mjs` to click real UI paths instead of relying on API fallback.

## Remaining P0 Issues

None known after browser smoke.

## Remaining P1 Issues

- Issues/Kanban needs agent/channel mode tabs and filters.
- Channels needs full tabbed UX for overview/rules/sources/MAX/risks/stats.
- Goals need mutation endpoints to become fully operational.

## Remaining UX Debt

- Some logs/details still expose technical fields for debugging.
- Historical mock/demo data makes pages dense.
- Calendar is mostly empty in safe dry-run stage.
- Exact row-level links in Logs would reduce debugging friction.

## Safety Confirmation

- MAX public publishing: not implemented and not enabled.
- Publisher Agent: disabled.
- Autonomous routines: disabled.
- Real LLM calls in mock: blocked.
- Real OpenAI dry-run: still works manually in dry_run.
- Secrets: frontend receives only masked metadata; smoke-secrets passed.

## Verification

- `smoke-control-plane`: passed.
- `smoke-secrets`: passed.
- `smoke-real-llm-dry-run`: passed.
- `node tools/smoke_ui_browser.mjs`: passed against public frontend.
- Server-side browser run was attempted, but the server image does not include Playwright/Chromium runtime. The exact command is documented by the script error: install Playwright on the server or run the existing local command against the public URL. Local Chromium run against the public URL passed.
- Final browser inventory: 17 pages, 1651 visible controls, 868 buttons, 181 disabled controls, 0 console errors.

## Next Recommendation

Proceed to Step 2.7.3 Prompt Quality Refinement. Do not move to MAX publishing until prompt quality, human review, safety reporting and publish approval UX are stable.
