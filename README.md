# ERA Media Factory

AI-powered media orchestration platform for managing multiple MAX messenger channels.

## MVP stack

- Backend: FastAPI, SQLAlchemy, Alembic, Pydantic
- Queue: Redis + Celery + Celery Beat placeholder
- Database: PostgreSQL
- Frontend: Next.js / React
- Agents: custom Python orchestrator with mock and real LLM dry-run providers
- MAX: adapter interface; public publishing is intentionally blocked until the adapter is implemented

## Start

```bash
cp .env.example .env
# set APP_SECRET_KEY to a long random value
BACKEND_PORT=18000 FRONTEND_PORT=13000 docker compose up --build
```

Ports bind to `127.0.0.1` by default. Use `BIND_HOST=0.0.0.0` only behind a firewall, VPN, or authenticated reverse proxy.

Backend: http://localhost:8000
Frontend: http://localhost:3000
Healthcheck: http://localhost:8000/health

Useful MVP checks:

```bash
make demo-data
make smoke-test
make smoke-control-plane
```

## Current safety posture

- Default system mode is safe/mock.
- Public publishing is disabled.
- Human review is required before publication.
- Secrets must stay in `.env` or encrypted DB storage, never in git.
- Do not expose the API publicly until authentication or a protected reverse proxy is added.
