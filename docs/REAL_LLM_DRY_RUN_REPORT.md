# Step 2.7 Real LLM Dry-Run Report

## Summary

- Overall status: implemented and ready for smoke verification on the server.
- Ready for Step 2.7 usage: yes, in `system_mode=dry_run` only.
- Ready for MAX publishing: no.
- Publisher Agent: remains disabled by design.
- Autonomous routines: not enabled.

## Implemented

- Added explicit post generation metadata:
  - `generation_mode`
  - `provider`
  - `model`
  - `prompt_template_version`
  - `publishable`
  - `non_publishable_reason`
  - `tokens_input`
  - `tokens_output`
  - `estimated_cost_usd`
  - `llm_trace_id`
  - `structured_outputs_json`
- Added Alembic migration `0008_real_llm_dry_run.py`.
- Added Alembic migration `0009_unschedule_nonpub.py` to clean old scheduled mock/dry-run posts.
- Added structured JSON contracts for:
  - `ResearchOutput`
  - `FactcheckOutput`
  - `EditorOutput`
  - `ChiefEditorOutput`
- Updated provider layer so OpenAI, Anthropic, Gemini, Ollama and mock return parsed structured JSON.
- Added one retry for invalid structured JSON responses.
- Added manual real dry-run pipeline:
  - `POST /api/topics/{topic_id}/run-dry-run`
  - Topic -> Research -> Factcheck -> Editor -> Chief Editor -> Post in review queue.
- Added Topics UI button: `LLM dry-run`.
- Added Posts UI visibility for:
  - mock/dry_run/live badge
  - provider/model/prompt version
  - token usage
  - cost
  - publishable state
  - non-publishable reason
- Added Dashboard visibility for:
  - real LLM allowed state
  - MAX publishing state
  - mock/dry_run/live post counts
  - real LLM calls today
  - cost today
- Added Agent detail provider readiness:
  - env key present
  - dry-run ready/not ready
  - provider/model
  - reason
- Added cost/activity logging for provider test calls.
- Added smoke target:
  - `make smoke-real-llm-dry-run`

## Safety Rules

- Mock mode never makes real provider calls.
- Mock posts are never publishable.
- Dry-run posts are never public-publishable.
- `approve` and `schedule` now require `post.publishable=true`.
- Manual post save cannot mutate protected generation/publishing fields.
- MAX publishing is not called by the dry-run pipeline.
- Publisher Agent is not assigned work by this step.
- Routines are not enabled.

## Smoke Behavior

- If no `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or `GEMINI_API_KEY` is configured:
  - `make smoke-real-llm-dry-run` exits successfully with a skip message.
- If a provider key is configured:
  - temporarily switches to `dry_run`
  - configures Research/Factcheck/Editor/Chief Editor for the real provider
  - creates a source-backed test topic
  - runs the dry-run pipeline
  - verifies a `needs_review` dry-run post
  - verifies provider/model/token/cost traces
  - restores prior settings/configs

## Remaining Notes

- Real LLM generation depends on valid provider keys and selected model availability.
- `live` mode fields exist for future use, but live publishing is intentionally not implemented here.
- `npm run lint` is not usable with the current Next.js 16 script (`next lint` is no longer valid in this setup); `npm run build` passes.

## Next Recommended Step

Run `make smoke-real-llm-dry-run` on the server. If it skips because provider keys are absent, configure one provider key and rerun. After successful dry-run verification, continue Step 2.7 refinement around prompt quality and cost calibration. Do not move to MAX publishing yet.
