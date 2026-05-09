# ERA Media Factory Control Plane Audit Report

Audit date: 2026-04-30

## Summary

- Overall status: Working for Step 2.6 core, with UX/decorative backlog documented.
- Readiness score: 88/100.
- Ready for Step 2.7: Yes, for Real LLM Dry-Run work, as long as MAX publishing remains disabled.
- Ready for MAX publishing: No.

## Working

- Public frontend is reachable at `http://194.87.243.63:13000/`.
- Public backend health is reachable at `http://194.87.243.63:18000/health`.
- Docker Compose runs backend, frontend, Postgres, Redis, worker and scheduler.
- Alembic is at `0007_operating_loop_kanban (head)`.
- Seed data exists for 5 channels and 19 agents.
- Safety defaults are intact: `mock` mode, global agents disabled, global routines disabled, global publishing disabled.
- `operating_loop_runs` model/table exists.
- `POST /api/operating-loop/run` and `GET /api/operating-loop/latest` exist.
- Manual CEO Loop runs planning-only when `global_agents_enabled=false`.
- CEO Loop creates Daily Content Plan, parent issue and expected sub-issues.
- CEO Loop writes operating report, activity events and decision logs.
- Publisher Agent receives no work in checked flows.
- Real LLM calls are not executed in mock mode.
- MAX public publishing is not called.
- Mock posts are marked `mock_only` and contain `not_publishable_reason`.
- Mock posts cannot be approved or scheduled.
- Kanban state machine blocks illegal transitions with 422 and logs `issue_transition_rejected`.
- Issue detail exposes parent/sub-issues, owner, reviewer, decision logs and activity.
- Agent config opens and saves.
- Prompt templates save and version when content changes.
- MAX integration shows `https://platform-api.max.ru` and masks token data.

## Broken

- Browser-level Playwright smoke is not fully stable in the current local Codex Windows environment: it may fail browser launch with `EPERM` or time out on `networkidle`. The strict API-backed UI smoke fallback passes.
- Goals are read-only; create/save/pause/achieve/fail workflows are not implemented.
- Logs are read-only; filters and refresh are not implemented.
- Calendar has no open-post action.
- Notifications have no archive action.

## Decorative / Not Real Yet

- Goals look like a control-plane section but are currently display-only.
- Logs are a passive table, not an operational log console.
- LLM provider settings exist, but real provider execution is intentionally blocked in mock.
- Routines can be configured and dry-run, but autonomous routine execution is globally disabled.
- MAX integration can be tested/admin-tested, but public publishing is intentionally absent.

## Safety Issues

- No active public MAX publishing path was found.
- Publisher Agent remains blocked by backend from being resumed.
- Mock posts remain not publishable.
- Real LLM calls are blocked in mock mode.
- Routines are disabled globally by default.
- Fixed during audit: parent issue completion now requires terminal sub-issues to have `result_summary`, not only failed sub-issues.

## UX Issues

- Several labels and statuses are still technical: `ready`, `in_progress`, `mock`, `provider`, `max_runs_per_day`.
- Some English remains: `Health`, `Dry run`, `Success rate`.
- Dashboard safety settings save immediately without clear saved feedback.
- Integration and agent detail pages are accurate but technical.
- Empty states exist but not all explain what to do next.

## Fixed During Audit

- Alembic revision id was shortened earlier so migrations can apply on Postgres.
- Public frontend/backend ports were verified and server deployment was restored.
- Parent issue completion rule was tightened.
- Manual Kanban transitions now create decision logs.
- Source and channel deletes now create activity events.
- Dashboard now exposes mock/not-publishable post counts.
- Integration copy-env label was translated to Russian.
- Post copy action now gives feedback.
- `/api/ui/button-contracts` was expanded to reflect more visible real buttons.
- `tools/smoke_ui.mjs` now checks illegal transitions, mock scheduling block, MAX base URL, token masking, notifications and prompt activity. It falls back to strict API-backed checks if browser spawn is unavailable.

## Still Needs Work

- Browser-level Playwright should be stabilized later in CI or a clean browser runtime; current `smoke-ui` fallback passes and catches API/state regressions.
- Add browser automation in an environment where Chrome can launch, or run it in CI/server.
- Add editable Goals only if goal management is required before Step 2.7.
- Add Logs filters/refresh if Logs should be operational.
- Translate common technical statuses and mixed English labels.
- Add confirmation for destructive source delete.
- Add explicit generation mode metadata before Step 2.7 to split mock/dry_run/live posts exactly.

## Next Recommended Step

Proceed to Step 2.7 Real LLM Dry-Run. Do not start MAX publishing until Step 2.7 has been implemented and audited successfully.
