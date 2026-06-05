# Zero Token Intake Report

## Verified zero-token steps

- RSS/source fetch
- article extraction
- deduplication
- source item and topic scoring
- MAX package formatting
- source preview media lookup when `generate_fallback=false`

## Verification result

- agent_runs delta: 0
- cost_events delta: 0
- input tokens delta: 0
- output tokens delta: 0
- estimated cost delta: 0.0

## Still not zero-token

- draft writing / translation / rewrite
- senior agenda LLM pass
- editorial quality loop when it uses an LLM
- generated visuals

Relay channels must label source scanning as zero-token, but Russian rewrite remains a paid LLM step unless replaced by templates or a local model.
