# Zero Token Intake Report

## What is guaranteed zero-token

- RSS/source fetch.
- Article extraction from public pages.
- Deduplication.
- Freshness scoring.
- Basic source/topic scoring.
- Radar listing.
- Daily edition candidate collection.
- MAX text packaging and source cleanup.
- Source preview media lookup when `generate_fallback=false`.

These steps must not create `agent_runs`, `cost_events`, OpenAI calls, token usage, or image generation calls.

## What still costs tokens

- Draft writing, translation and rewrite.
- Senior journalist agenda.
- Editorial quality loop when it uses an LLM.
- Chief editor LLM review.
- Generated visuals.
- Relay rewrite for channels such as Financial Times po-russki.

## Guardrail

`make smoke-zero-token-intake` verifies that the zero-token intake path creates no `agent_runs`, no `cost_events`, no token usage and no estimated cost.

If this smoke fails, the collection path is no longer truly zero-token and must not be described as free.

## Product rule

The system must separate two modes:

- Intake: collect, dedupe, score, list, package, and find preview media without LLM.
- Editorial generation: use LLM only when Russian text, interpretation, rewrite, or high-risk verification is actually needed.
