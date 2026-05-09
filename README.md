# ERA Media Factory

AI-powered media orchestration platform for managing multiple MAX messenger channels.

## MVP stack

- Backend: FastAPI, SQLAlchemy, Alembic, Pydantic
- Queue: Redis + Celery + Celery Beat placeholder
- Database: PostgreSQL
- Frontend: Next.js / React
- Agents: custom Python orchestrator with mock LLM provider
- MAX: adapter interface with stub implementation

## Start

```bash
docker compose up --build
```

If local ports are busy:

```bash
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
```

On backend startup Docker Compose runs:

```bash
alembic upgrade head
python -m app.seed
```

## First pipeline

The MVP pipeline is intentionally bounded and finite:

1. Create or use a topic.
2. Score the topic.
3. Generate a draft with the mock LLM provider.
4. Save the post to the review queue.
5. Save task and agent run logs.

Trigger it:

```bash
curl -X POST http://localhost:8000/api/topics/1/generate-draft
```
