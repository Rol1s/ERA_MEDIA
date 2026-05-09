.PHONY: demo-data smoke-test smoke-control-plane smoke-ui smoke-ui-browser smoke-real-llm-dry-run smoke-prompt-quality smoke-source-ingestion smoke-first-edition smoke-secrets

BACKEND_PORT ?= 8000

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

smoke-first-edition:
	curl -fsS http://localhost:$(BACKEND_PORT)/health
	docker compose exec -T backend python -m app.smoke_first_edition

smoke-secrets:
	curl -fsS http://localhost:$(BACKEND_PORT)/health
	docker compose exec -T -e APP_SECRET_KEY=smoke-secret-key backend python -m app.smoke_secrets
