# ERA Media Factory: MAX Publication Handoff

## Purpose

This package contains the code and context needed to understand and continue the MAX publication technology for ERA Media Factory.

The goal is not to rebuild the whole newsroom. The goal is to let another agent/developer understand how a generated post becomes a MAX publication.

## Main Flow

```text
Post
-> quality / approval guards
-> prepare_max_package()
-> prepare_media_for_post()
-> publish_to_max()
-> _send_max_payload()
-> MAX API
```

## Key Files

### Publication API

- `backend/app/api/routes/posts.py`

Contains:

- `publish_to_max(...)`
- `_send_max_payload(...)`
- `_send_max_message(...)`
- `_send_max_message_with_attachment(...)`
- approve/reject/save/quality-check/media/package endpoints

### MAX Text Packaging

- `backend/app/services/max_packaging.py`

Responsible for:

- bold headline
- short MAX-ready text
- one public source
- hiding RSS/XML feed links
- MAX buttons metadata

### Media

- `backend/app/services/media_producer.py`
- `backend/app/services/visual_media.py`
- `backend/app/services/public_sources.py`

Responsible for:

- finding `og:image`, `twitter:image`, RSS media/enclosure
- avoiding fake generated evidence on high-risk news
- optional generated visuals
- source URL cleanup

### Channel / MAX Configuration

- `backend/app/api/routes/control_plane.py`
- `backend/app/api/routes/channels.py`
- `backend/app/models/all_models.py`

Important model:

- `PlatformChannel`

This stores the MAX chat/channel binding.

### Owner Bot

- `backend/app/api/routes/owner_bot.py`

Used for Telegram control commands and public submissions.

### Relay / Autopublish

- `backend/app/services/ft_live_monitor.py`
- `backend/app/services/auto_publisher.py`
- `backend/app/services/editorial_autopilot.py`
- `backend/app/api/routes/autopublish.py`
- `backend/app/api/routes/relays.py`

Use carefully. Autopublish must not be enabled without explicit owner approval.

## Database

Models are in:

- `backend/app/models/all_models.py`

Important tables:

- `posts`
- `channels`
- `platform_channels`
- `source_items`
- `topics`
- `activity_events`
- `cost_events`
- `agent_runs`
- `newsroom_submissions`

Migrations are in:

- `backend/alembic/versions`

Important migrations:

- `0018_launch_readiness_manual_metrics.py`
- `0020_newsroom_v1.py`
- `0021_cost_optimizer_relays.py`

## Safety Rules

- Do not expose secrets.
- Do not log bot/API tokens.
- Do not publish mock/demo content.
- Do not show RSS/XML source links to readers.
- Do not publish high-risk content without quality guard / approval unless owner explicitly changes policy.
- Generated images must not be presented as event evidence.

## Zero-token Boundary

These must stay zero-token:

- source fetch
- RSS parse
- dedupe
- freshness score
- radar
- candidate collection
- media preview lookup
- MAX packaging

Smoke:

```bash
make smoke-zero-token-intake
```

## Useful Smoke Tests

```bash
make smoke-max-packaging
make smoke-media-producer
make smoke-owner-bot
make smoke-ft-live-cheap
make smoke-zero-token-intake
```

## VPS

Project path:

```text
/opt/era-media-factory
```

Common deploy:

```bash
cd /opt/era-media-factory
docker compose build backend worker scheduler
docker compose up -d backend worker scheduler
```

Frontend:

```bash
docker compose build frontend
docker compose up -d frontend
```

## Local Path

```text
C:\Users\User\Documents\Codex\2026-05-09\era-media-factory\repo
```

## First Reading Order

1. `backend/app/api/routes/posts.py`
2. `backend/app/services/max_packaging.py`
3. `backend/app/services/media_producer.py`
4. `backend/app/models/all_models.py`
5. `backend/app/api/routes/control_plane.py`
6. `docs/RICH_MEDIA_NEWSROOM_REPORT.md`
7. `docs/ZERO_TOKEN_INTAKE_REPORT.md`
