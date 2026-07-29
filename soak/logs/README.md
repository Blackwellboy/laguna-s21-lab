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
| sessions with status `completed` | 400 |
| sessions with status `killed` at the session token cap | 9 |
| `turns.jsonl` lines | 3,099 |
| turn records | 3,096 |
| turn records with `http_status` 200 | 3,096 |
| `kind: integrity_probe` records interleaved in the same file | 3 |
| unique `session_id` in turns | 409 |

Every turn `session_id` appears in `sessions.jsonl`.

**The three rows that carry no `http_status` are not turns** (corrected
2026-07-29). They are `kind: integrity_probe` records, a different shape with
`probe_id`, `status`, `refused` and `response_len` and no `session_id` and no
`turn`. They are the same three records as `integrity_probes.jsonl`, written
into this file as well by the probe path in `../soak_driver.py`, with the
verbatim response replaced by a length counter. All three carry `status: 200`
and `http_error: false`.

An earlier version of this note called them "the incomplete in-flight records
at cut". That was wrong, and it is disprovable from `integrity_probes.jsonl`
in this directory.

**All 3,096 turn records returned HTTP 200.** The turn log in
`../soak_driver.py` is written unconditionally with whatever status came back,
so a failed turn would appear here with a non-200 status. None do.

Also here: `sessions.jsonl`, `incidents.jsonl`, `integrity_probes.jsonl`,
`service_samples.jsonl`.

Full redaction history: `../../REDACTIONS.md`.
