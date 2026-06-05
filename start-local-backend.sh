#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/hermes/ERA_MEDIA"
PGROOT="/home/hermes/.local/pg16"
PGDATA="/home/hermes/.local/era_pgdata"
REDISROOT="/home/hermes/.local/redis"

export PATH="$PGROOT/usr/lib/postgresql/16/bin:$PATH"
export LD_LIBRARY_PATH="$PGROOT/usr/lib/x86_64-linux-gnu:$PGROOT/usr/lib/postgresql/16/lib:${LD_LIBRARY_PATH:-}"

if ! pg_ctl -D "$PGDATA" status >/dev/null 2>&1; then
  pg_ctl -D "$PGDATA" -o "-k $PGDATA -h 127.0.0.1 -p 15432" -l /home/hermes/.local/era_pg.log start
fi

if ! /home/hermes/.local/redis/usr/bin/redis-cli -h 127.0.0.1 -p 16379 ping >/dev/null 2>&1; then
  (LD_LIBRARY_PATH="$REDISROOT/usr/lib/x86_64-linux-gnu" "$REDISROOT/usr/bin/redis-server" --bind 127.0.0.1 --port 16379 --save '' --appendonly no > /home/hermes/.local/era_redis.log 2>&1 &)
fi

cd "$ROOT/backend"
source "$ROOT/.venv/bin/activate"
if [ -f "$ROOT/.env.local" ]; then
  set -a
  source "$ROOT/.env.local"
  set +a
fi
export DATABASE_URL='postgresql+psycopg2://hermes@127.0.0.1:15432/era_media'
export REDIS_URL='redis://127.0.0.1:16379/0'
export CELERY_BROKER_URL='redis://127.0.0.1:16379/1'
export CELERY_RESULT_BACKEND='redis://127.0.0.1:16379/2'
export ERA_MEDIA_ROOT="$ROOT/media/generated"

alembic upgrade head
PYTHONPATH=. python -m app.seed
exec python -m uvicorn app.main:app --host 127.0.0.1 --port "${BACKEND_PORT:-18000}"
