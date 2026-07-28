# Soak logs

## `turns.jsonl` (republished 2026-07-29)

The raw per-turn log of the 12h soak. Withdrawn on 2026-07-28 after a whole-tree
re-scan found internal identifiers in its **model-generated response previews**.
Republished on 2026-07-29 with those free-text preview fields removed and
replaced by `*_chars` length counters so the structural measurements stay
checkable without carrying model prose that quotes the private ingest corpus.

Fields kept include session id, persona, turn index, `http_status`, latencies,
thinking flags and token counters, tool_success, cumulative session tokens,
incident flag, and timestamp.

### Counts a reader can re-derive

| Source | Count |
|---|---|
| `sessions.jsonl` lines | 409 |
| unique `session_id` in sessions | 409 |
| `turns.jsonl` lines | 3,099 |
| turns with `http_status` 200 | 3,096 |
| turns with `http_status` null | 3 |
| unique `session_id` in turns (including null) | 410 |

Every non-null turn `session_id` appears in `sessions.jsonl`. The three
null-status rows are the incomplete in-flight records at cut. The scorecard
in `../LAGUNA_SOAK_12H_20260725_RESULTS.md` reports 409 sessions and 3,096
HTTP-200 turns on purpose.

Also here: `sessions.jsonl`, `incidents.jsonl`, `integrity_probes.jsonl`,
`service_samples.jsonl`.

Full redaction history: `../../REDACTIONS.md`.
