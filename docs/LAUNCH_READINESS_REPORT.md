# Launch Readiness Report

Date: 2026-05-10

## Scope

This release prepares ERA Media Factory for the first real text-publication launch path. It does not enable auto-publishing and does not call MAX.

## Backup

Backup path is recorded during VPS deployment. If the backup is not created, deployment must stop before cleanup.

## Added

- `GET /api/launch/readiness`
- `POST /api/launch/cleanup-generated-content`
- `POST /api/launch/run-text-cycle`
- `POST /api/posts/{id}/mark-published-manually`
- `GET /api/metrics/posts`
- `POST /api/metrics/posts/{post_id}`
- `/launch` Launch Control page
- `production_manual` system mode
- `archived_generated_content` archive table
- extended manual post metrics
- `make smoke-launch-readiness`

## Modes

- `mock`: dev/test mode. Mock provider is allowed, publishing is forbidden, generated content is never publishable.
- `dry_run`: real-ish pipeline mode. Publishing is forbidden and generated content is not publishable.
- `production_manual`: real sources, real LLM provider, editorial voice, factcheck, review queue and manual copy workflow. Mock provider is forbidden in the launch path. Publishing API remains disabled.
- `production_auto`: future mode, not enabled.

## Safety

- Mock content cannot be marked publishable.
- Dry-run content cannot become publishable through normal cleanup/launch paths.
- Publisher Agent remains disabled.
- MAX cannot be called while publishing is disabled.
- Generated-content cleanup archives payloads before hiding records.

## Cleanup

Cleanup supports preview and confirmed archive mode. It does not touch:

- sources;
- channels;
- settings;
- activity events;
- decision logs;
- issues, except future publish-related reset if needed.

## Human Actions

Before the first seven-day cycle:

- keep `system_mode=production_manual`;
- verify OpenAI provider status;
- health-check core sources;
- run a small text cycle;
- review generated posts;
- copy ready posts manually;
- mark manually published posts;
- enter basic metrics manually.

## Known Blockers

MAX API publishing is intentionally not configured for launch. If the daily token guard is already exhausted, generation must wait for the next budget window or receive a controlled operator override.
