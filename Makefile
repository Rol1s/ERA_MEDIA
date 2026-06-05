.PHONY: demo-data smoke-test smoke-control-plane smoke-ui smoke-ui-browser smoke-real-llm-dry-run smoke-prompt-quality smoke-source-ingestion smoke-rsshub-source-adapter smoke-first-edition smoke-secrets smoke-freshness-logic smoke-source-balance smoke-live-radar-quality smoke-agency-operating-loop smoke-editorial-voice-system smoke-editorial-director smoke-editorial-quality-loop newsroom-clean-slate-sources smoke-launch-readiness smoke-editor-day smoke-media-producer smoke-max-packaging smoke-owner-bot smoke-cost-optimizer smoke-zero-token-intake smoke-relay-channel smoke-ft-live-cheap smoke-daily-package smoke-ollama-provider-health smoke-brain-mode-local-gemma smoke-local-mode-blocks-openai smoke-local-mode-blocks-mock-operator-path smoke-agent-contract-registry smoke-agent-contract-versioning smoke-agent-run-contract-artifacts smoke-contract-compatibility-handoff smoke-contract-escalation smoke-agent-workbench-api smoke-local-brain-benchmark-thresholds smoke-editorial-contract-microsteps smoke-quality-loop-editorial-claim-filter smoke-senior-journalist-contract-repair smoke-local-mode-ignores-paid-token-budget smoke-max-channel-workspace smoke-channel-fit-contracts smoke-story-generation-dedupe

BACKEND_PORT ?= 18000

demo-data:
	curl -fsS -X POST http://localhost:$(BACKEND_PORT)/api/dev/demo-data

smoke-test:
	curl -fsS http://localhost:$(BACKEND_PORT)/health
	docker compose exec -T backend python -m app.smoke_test

smoke-control-plane:
	curl -fsS http://localhost:$(BACKEND_PORT)/health
	docker compose exec -T backend python -m app.smoke_control_plane

smoke-ui:
	node tools/smoke_ui.mjs

smoke-ui-browser:
	node tools/smoke_ui_browser.mjs

smoke-real-llm-dry-run:
	curl -fsS http://localhost:$(BACKEND_PORT)/health
	docker compose exec -T backend python -m app.smoke_real_llm_dry_run

smoke-prompt-quality:
	curl -fsS http://localhost:$(BACKEND_PORT)/health
	docker compose exec -T backend python -m app.smoke_prompt_quality

smoke-source-ingestion:
	curl -fsS http://localhost:$(BACKEND_PORT)/health
	docker compose exec -T backend python -m app.smoke_source_ingestion

smoke-rsshub-source-adapter:
	curl -fsS http://localhost:$(BACKEND_PORT)/health
	docker compose exec -T backend python -m app.smoke_rsshub_source_adapter

smoke-first-edition:
	curl -fsS http://localhost:$(BACKEND_PORT)/health
	docker compose exec -T backend python -m app.smoke_first_edition

smoke-secrets:
	curl -fsS http://localhost:$(BACKEND_PORT)/health
	docker compose exec -T -e APP_SECRET_KEY=smoke-secret-key backend python -m app.smoke_secrets

smoke-freshness-logic:
	curl -fsS http://localhost:$(BACKEND_PORT)/health
	docker compose exec -T backend python -m app.smoke_freshness_logic

smoke-source-balance:
	curl -fsS http://localhost:$(BACKEND_PORT)/health
	docker compose exec -T backend python -m app.smoke_source_balance

smoke-live-radar-quality:
	curl -fsS http://localhost:$(BACKEND_PORT)/health
	docker compose exec -T backend python -m app.smoke_live_radar_quality

smoke-agency-operating-loop:
	curl -fsS http://localhost:$(BACKEND_PORT)/health
	docker compose exec -T backend python -m app.smoke_agency_operating_loop

smoke-editorial-voice-system:
	curl -fsS http://localhost:$(BACKEND_PORT)/health
	docker compose exec -T backend python -m app.smoke_editorial_voice_system

smoke-editorial-director:
	curl -fsS http://localhost:$(BACKEND_PORT)/health
	docker compose exec -T backend python -m app.smoke_editorial_director

smoke-senior-journalist-contract-repair:
	curl -fsS http://localhost:$(BACKEND_PORT)/health
	docker compose exec -T backend python -m app.smoke_senior_journalist_contract_repair

smoke-editorial-quality-loop:
	curl -fsS http://localhost:$(BACKEND_PORT)/health
	docker compose exec -T backend python -m app.smoke_editorial_quality_loop

newsroom-clean-slate-sources:
	curl -fsS http://localhost:$(BACKEND_PORT)/health
	docker compose exec -T backend python -m app.newsroom_reset_and_source_seed

smoke-launch-readiness:
	curl -fsS http://localhost:$(BACKEND_PORT)/health
	docker compose exec -T backend python -m app.smoke_launch_readiness

smoke-editor-day:
	curl -fsS http://localhost:$(BACKEND_PORT)/health
	docker compose exec -T backend python -m app.smoke_editor_day

smoke-media-producer:
	curl -fsS http://localhost:$(BACKEND_PORT)/health
	docker compose exec -T backend python -m app.smoke_media_producer

smoke-max-packaging:
	curl -fsS http://localhost:$(BACKEND_PORT)/health
	docker compose exec -T backend python -m app.smoke_max_packaging

smoke-max-channel-workspace:
	curl -fsS http://localhost:$(BACKEND_PORT)/health
	docker compose exec -T backend python -m app.smoke_max_channel_workspace

smoke-channel-fit-contracts:
	curl -fsS http://localhost:$(BACKEND_PORT)/health
	docker compose exec -T backend python -m app.smoke_channel_fit_contracts

smoke-story-generation-dedupe:
	curl -fsS http://localhost:$(BACKEND_PORT)/health
	docker compose exec -T backend python -m app.smoke_story_generation_dedupe

smoke-owner-bot:
	curl -fsS http://localhost:$(BACKEND_PORT)/health
	docker compose exec -T backend python -m app.smoke_owner_bot

smoke-cost-optimizer:
	curl -fsS http://localhost:$(BACKEND_PORT)/health
	docker compose exec -T backend python -m app.smoke_cost_optimizer

smoke-zero-token-intake:
	curl -fsS http://localhost:$(BACKEND_PORT)/health
	docker compose exec -T backend python -m app.smoke_zero_token_intake

smoke-relay-channel:
	curl -fsS http://localhost:$(BACKEND_PORT)/health
	docker compose exec -T backend python -m app.smoke_relay_channel

smoke-ft-live-cheap:
	curl -fsS http://localhost:$(BACKEND_PORT)/health
	docker compose exec -T backend python -m app.smoke_ft_live_cheap

smoke-daily-package:
	curl -fsS http://localhost:$(BACKEND_PORT)/health
	docker compose exec -T backend python -m app.smoke_daily_package

smoke-ollama-provider-health:
	curl -fsS http://localhost:$(BACKEND_PORT)/health
	docker compose exec -T backend python -m app.smoke_ollama_provider_health

smoke-brain-mode-local-gemma:
	curl -fsS http://localhost:$(BACKEND_PORT)/health
	docker compose exec -T backend python -m app.smoke_brain_mode_local_gemma

smoke-local-mode-blocks-openai:
	curl -fsS http://localhost:$(BACKEND_PORT)/health
	docker compose exec -T backend python -m app.smoke_local_mode_blocks_openai

smoke-local-mode-ignores-paid-token-budget:
	curl -fsS http://localhost:$(BACKEND_PORT)/health
	docker compose exec -T backend python -m app.smoke_local_mode_ignores_paid_token_budget

smoke-local-mode-blocks-mock-operator-path:
	curl -fsS http://localhost:$(BACKEND_PORT)/health
	docker compose exec -T backend python -m app.smoke_local_mode_blocks_mock_operator_path

smoke-agent-contract-registry:
	curl -fsS http://localhost:$(BACKEND_PORT)/health
	docker compose exec -T backend python -m app.smoke_agent_contract_registry

smoke-agent-contract-versioning:
	curl -fsS http://localhost:$(BACKEND_PORT)/health
	docker compose exec -T backend python -m app.smoke_agent_contract_versioning

smoke-agent-run-contract-artifacts:
	curl -fsS http://localhost:$(BACKEND_PORT)/health
	docker compose exec -T backend python -m app.smoke_agent_run_contract_artifacts

smoke-editorial-contract-microsteps:
	curl -fsS http://localhost:$(BACKEND_PORT)/health
	docker compose exec -T backend python -m app.smoke_editorial_contract_microsteps

smoke-quality-loop-editorial-claim-filter:
	curl -fsS http://localhost:$(BACKEND_PORT)/health
	docker compose exec -T backend python -m app.smoke_quality_loop_editorial_claim_filter

smoke-contract-compatibility-handoff:
	curl -fsS http://localhost:$(BACKEND_PORT)/health
	docker compose exec -T backend python -m app.smoke_contract_compatibility_handoff

smoke-contract-escalation:
	curl -fsS http://localhost:$(BACKEND_PORT)/health
	docker compose exec -T backend python -m app.smoke_contract_escalation

smoke-agent-workbench-api:
	curl -fsS http://localhost:$(BACKEND_PORT)/health
	docker compose exec -T backend python -m app.smoke_agent_workbench_api

smoke-local-brain-benchmark-thresholds:
	curl -fsS http://localhost:$(BACKEND_PORT)/health
	docker compose exec -T backend python -m app.smoke_local_brain_benchmark_thresholds
