# Feedloom Architecture

## Purpose and boundary

Feedloom is a collector-only repository for a daily AI and data-science briefing. The collector gathers and normalizes candidate stories; a separate Codex task selects and formats a briefing from that JSON. Collection and selection are deliberately separate so an unavailable source or incomplete window remains visible.

## Data flow

```text
RSS / official pages / lists / release feeds
                 ↓
scripts/ai_news_collect.py + source helpers
                 ↓
candidate JSON (latest / reading + collection_errors)
                 ↓
briefing task selects a bounded set
                 ↓
optional explicitly authorized Gmail delivery
                 ↓
selected IDs marked in state/ai_news_seen.json
```

`scripts/anthropic_sources.py` and `scripts/uber_sources.py` contain source-specific extraction. `scripts/ai_news_collect.py` owns the time windows, normalization, topic/depth signals, deduplication, error collection, and `--mark-seen` state update. Tests under `tests/` cover collector behavior and source parsing.

The `latest` lane uses a short recent window; the `reading` lane looks back farther but requires depth signals. The collector does not promise complete historical coverage, and a single source error should not discard usable candidates. Candidate IDs are the only input the downstream briefing selection may use.

## Delivery boundary

- Preview and draft work reads candidates only and does not send mail or mark items seen.
- Gmail is used only when a user or existing task explicitly authorizes a specified recipient. Delivery must be confirmed before selected IDs are recorded.
- `state/ai_news_seen.json` is runtime state and stays out of Git.
- Validate source maintenance with `python3 -m unittest discover -s tests -v`; inspect coverage notes when a source is rate-limited or unavailable.
