# Source Ingestion Report

## Summary

- source types implemented: rss, website, manual_url, api_placeholder, ladder_optional disabled
- smoke RSS source used: https://www.nasa.gov/rss/dyn/breaking_news.rss
- smoke public URL used: https://www.cdc.gov/sleep/about/index.html
- RSS items fetched: 1
- RSS topics created: 1
- duplicate items on second run: 1
- website extraction status: extracted
- dry-run generation from ingested topic: passed
- dry-run post id: 43
- MAX publish called: no
- Publisher assigned work: no

## Extraction Quality Notes

- Extraction removes script/style/navigation/header/footer-like blocks and keeps headings, paragraphs, lists and blockquotes.
- Pages with login/paywall/subscription markers are marked blocked and are not used as ready topics.
- Full source text is stored for internal analysis; generated posts must summarize with added value and must not republish large article fragments.

## Safety Notes

- Ladder optional remains disabled by default.
- No paywall bypass is implemented.
- No MAX publishing is implemented.
- Publisher Agent remains disabled.

## Next Step Recommendation

- Improve source-specific extraction heuristics and add operator curation before any autonomous discovery.
