# REAL OPENAI DRY-RUN REPORT

## Summary

- Provider used: openai
- Model used: gpt-5.4-mini
- System mode during test: dry_run
- Topic id: 21
- Post id: 19
- Post status: needs_review
- Generation mode: dry_run
- Structured outputs valid: yes
- Ready for prompt refinement: yes

## Provider Test

- Endpoint: POST /api/secrets/openai/OPENAI_API_KEY/test
- Result: passed
- Structured response: valid JSON
- Test model: gpt-5.4-mini
- Test tokens input/output: 46 / 14
- Test estimated cost USD: 0.0000975
- Secret exposure: no raw key returned; only masked_value was returned

## Pipeline Result

- Source-backed topic URL: https://developers.openai.com/api/docs/models
- Post title: "Как выбрать модель OpenAI для редакторских AI-агентов: практичный разбор без обещаний чудес"
- Agent runs count: 4
- Pipeline: Research -> Factcheck -> Editor -> Chief Editor -> Post needs_review
- Total tokens input/output: 3759 / 1641
- Estimated cost USD: 0.01020375
- Notification created for post: yes

## Agent Runs

| Agent | Status | Provider | Model | Input tokens | Output tokens | Estimated cost USD |
| --- | --- | --- | --- | ---: | ---: | ---: |
| research_agent | completed | openai | gpt-5.4-mini | 489 | 343 | 0.00191025 |
| factcheck_agent | completed_with_warnings | openai | gpt-5.4-mini | 727 | 294 | 0.00186825 |
| editor_agent | completed_with_warnings | openai | gpt-5.4-mini | 1087 | 742 | 0.00415425 |
| chief_editor_agent | completed | openai | gpt-5.4-mini | 1456 | 262 | 0.002271 |

## Post Quality Short Review

The post is suitable for a dry-run review queue: it is practical for ERA AI, explains model selection without promising unsupported results, and keeps publication blocked until human review. Factcheck/editor warnings are appropriate because the source-backed test still needs human validation before any public use.

## Failures / Warnings

- Fixed during verification: smoke-real-llm-dry-run previously skipped encrypted DB secrets and only checked env keys.
- Fixed during verification: smoke-secrets previously risked overwriting a real OpenAI secret; it now restores existing secret rows.
- Fixed during verification: smoke-control-plane counted historical real agent runs as mock-mode violations.
- Fixed during verification: test topic was too artificial and caused Research Agent rejection; replaced with a source-backed ERA AI topic.
- Fixed during verification: OpenAI strict JSON schema rejected free-form dict fields; unsupported arbitrary dict properties are now removed from strict schemas and defaulted by Pydantic.

## Safety

- MAX publish called: no
- Publisher assigned work: no
- Publisher runs: 0
- Publisher issues: 0
- Public publishing enabled: no
- Autonomous routines enabled: no
- Live mode enabled: no
- Dry-run post publishable: no
- Mock-only: no

## Conclusion

Step 2.7.1 OpenAI dry-run verification passed. The system is ready for prompt refinement and provider-readiness polishing, but not for MAX publishing.
