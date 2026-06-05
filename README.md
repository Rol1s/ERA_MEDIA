# ERA Media Factory

ERA Media Factory — маленькая AI-редакция для ведения MAX-канала «Нерв мира».

Продукт помогает выпускающему редактору:

- собирать новости из большого каталога источников;
- видеть свежий радар событий;
- получать редакционную повестку;
- выбирать темы для публикации;
- генерировать русскоязычные черновики;
- проверять смысл, источники и неподтверждённые claims;
- готовить медиа и MAX-упаковку;
- публиковать в MAX только после ручного approval.

## Главный принцип

Это не автопаблишер.

Публикация в MAX происходит только после явного действия человека. Автопубликация, Publisher Agent и автономная публикация не включены.

## Editorial Quality Loop v1

Перед approval/MAX каждый новый пост должен пройти обязательный quality loop:

1. `source/topic`
2. `evidence_pack`
3. `meaning_card`
4. `draft`
5. `claim-check`
6. `chief_editor`
7. `quality_loop`

Approval/MAX запрещены, если:

- нет `quality_loop.version = "v1"`;
- `quality_loop.passed != true`;
- есть `blocking_issues`;
- нет credible source/source_url;
- high-risk/hard-news не имеет primary source;
- generated image подаётся как доказательство;
- quality loop упал по parser/model/timeout error.

`quality_score` не перебивает blocking issues.

## Канал v1

Рабочий канал: «Нерв мира».

Редакционный стандарт:

- 5-8 постов в день;
- коротко, живо, по-русски;
- жёстко, но честно;
- факт отдельно от оценки;
- без шаблонов «Что произошло / Почему важно / Что дальше»;
- без фейковых фото и неподтверждённых claims.

## Stack

- Backend: FastAPI, SQLAlchemy, Alembic, Pydantic
- Queue: Redis + worker/scheduler layer
- Database: PostgreSQL
- Frontend: Next.js / React
- Agents: Python orchestrator + OpenAI provider
- Publishing: MAX API, только ручная публикация после approval

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

## Useful checks

```bash
make smoke-test
make smoke-editor-day
make smoke-media-producer
make smoke-max-packaging
make smoke-owner-bot
make smoke-editorial-quality-loop
```

## Optional local Fooocus visuals

Fooocus can be run locally in Docker as a separate image-generation UI for operator-reviewed MAX visuals.

```bash
make fooocus-up
```

UI:

```text
http://127.0.0.1:7865
```

Outputs are mounted to:

```text
./generated_media/fooocus
```

Full guide: [`docs/FOOOCUS_LOCAL.md`](docs/FOOOCUS_LOCAL.md)

## Operator guide

HTML-инструкция для сотрудника:

```text
/era-media-factory-guide.html
```

В ней описаны утренний сценарий, Редактор дня, Радар, Темы, Посты, Quality Loop, MAX, Telegram-бот и типовые ошибки.
