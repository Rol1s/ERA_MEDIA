# Operator UX Report

## Summary

Step 2.7.2 hardened the panel as an operator console for manual real LLM dry-run work. The UI now explains the next action, readiness blockers, disabled actions, and safety state without requiring the owner to read logs or browser console output.

- Readiness for prompt refinement: yes.
- Readiness for MAX publishing: no.
- MAX public publishing: disabled.
- Publisher Agent: disabled.
- Autonomous routines: disabled.

## What Changed

- Dashboard now starts with "Что делать дальше" and five operator action cards:
  - Подключить LLM
  - Подготовить агентов
  - Создать тему
  - Сгенерировать dry-run пост
  - Проверить пост
- Added reusable `SystemReadinessPanel` with Russian explanations and direct action links.
- Added global command bar:
  - Создать тему
  - Запустить dry-run
  - Посты на проверке
  - Настройки агентов
  - Проверить систему
- Redesigned Integrations as wizard-like provider setup:
  - secure key status
  - masked key only
  - model dropdown
  - structured provider test
  - bulk OpenAI setup for content agents
- Redesigned Agents page:
  - grouped agent cards
  - dry-run readiness
  - provider/model
  - runs and cost today
  - side drawer configuration
  - Publisher Agent clearly marked as disabled until publishing stage
- Added one-click OpenAI dry-run setup for content agents.
- Redesigned Topics page around readiness:
  - source URL
  - channel
  - dry-run blockers
  - mock draft and real dry-run actions
- Redesigned Posts page as review queue:
  - generation mode badges
  - provider/model/cost/tokens
  - editable preview
  - sources
  - creation and safety context
  - disabled publish/schedule reasons
- Redesigned Issues/Kanban with human-readable states and issue detail panel.
- Added visible toast feedback for operator actions.
- Added `make smoke-ui-browser` for real browser UI smoke.
- Hardened topic pipeline endpoints so controlled pipeline failures return 422 instead of 500.

## Disabled Buttons And Reasons

- Provider tests are disabled in mock mode because real LLM calls are forbidden there.
- OpenAI bulk setup is disabled if the OpenAI key or selected model is missing.
- Dashboard dry-run is disabled when system mode is not dry_run, OpenAI key is missing, content agents are not configured, no source-backed topic exists, or budget is blocked.
- Topic real dry-run is disabled when the topic has no source URL, no channel, system mode is mock, OpenAI is not configured, content agents are not ready, or budget is unavailable.
- Post approve/schedule remain disabled for mock and dry-run posts because public publishing is outside Step 2.7 and MAX publishing is still off.
- Publisher Agent actions remain disabled because publishing is not part of this step.
- Kanban shows only allowed transitions; illegal transitions remain blocked by backend state machine.

## Screenshots

No screenshots were committed in this step. Browser smoke covers the main operator paths.

## Verification

- Backend health: passed.
- Frontend public status: passed.
- Alembic migration status: `0010_integration_secrets`.
- `smoke-control-plane`: passed.
- `smoke-secrets`: passed.
- `smoke-real-llm-dry-run`: passed with a real provider call.
- Browser UI smoke: passed against `http://194.87.243.63:13000`.
- Local Windows shell did not have `make` installed, so the browser smoke target was verified by running its target command directly: `node tools/smoke_ui_browser.mjs`.
- `/favicon.ico`: returns 200.

## Remaining Rough Edges

- Some secondary pages still keep denser legacy layouts, especially where no Step 2.7.2 workflow change was required.
- Some technical values remain visible inside details and logs by design.
- Historical mock/demo data can still appear in the database and is marked by mode/badges where available.
- Browser smoke depends on Chromium or compatible browser availability on the local/server environment.

## Safety Confirmation

- No MAX public publishing was added.
- Publisher Agent remains disabled.
- Autonomous routines remain disabled.
- Real LLM provider tests are blocked in mock mode.
- Secrets remain masked in frontend metadata.

## Next Recommended Step

Proceed with prompt refinement and operator polish for dry-run content quality. Do not start MAX publishing until dry-run review, cost tracking, safety checks, and human approval flows are stable.
