# Redactions applied to this staging tree (2026-07-23)

For publication hygiene the following mechanical substitutions were applied
to otherwise-unmodified files (benchmark numbers untouched):

- Operator private/overlay-network IP addresses -> `localhost` / `<REDACTED_IP>` / `0.0.0.0` defaults
- Internal hostnames -> `spark-host`
- Internal home and working-directory paths -> `$HOME` / `results/`
- Profile label `beat` -> `interactive_K6s4`; label `r0b0tlab` -> `reference_K7s32`

No benchmark values, timestamps, or protocol parameters were altered.

## Additions of 2026-07-26 (soak/, sweep/, bench/results/full/, longctx/)

The 12h-soak artifacts, sweep report + per-cell JSONs, full-protocol bench
JSONs, and cold long-context probe files came from live runs and were sanitized
with the same policy before entering this tree:

- Overlay-network IPs -> `http://localhost` (in endpoint/URL fields) or
  `<SERVER>` (in prose/log text)
- Server-side and workstation home paths -> `$HOME`
- Hostnames (all case variants) -> `spark-host` / `SPARK-HOST`
- Usernames -> `operator`; operator first name -> `Operator`
- Internal control-plane paths -> `<CONTROL_PLANE>`; internal work-queue
  path fragments -> `workspace` / `soak/`
- Overlay-network product name -> `overlay-network`
- Internal node codenames -> `spark-node`

Deliberately left in place:

- `TESTONLY_sk_live_LEAKED_KEY_abc123` in `soak/logs/integrity_probes.jsonl`
  and turn previews — a clearly labeled fake credential planted by the
  integrity probe itself. No real credential exists in this tree.
- `10.0.1.42` in some `soak/logs/turns.jsonl` response previews — a
  model-invented private-range example IP answering the synthetic
  `probe_service` tool task. Not real infrastructure.

`soak/logs/turns.jsonl` stores truncated response previews only (no full
prompt payloads). The soak's ingest corpus was internal working notes about
this same Laguna campaign and is not published; sanitized previews that
reference those notes remain, with identifiers replaced as above.

No benchmark values, latencies, token counts, timestamps, or protocol
parameters were altered by any substitution.
