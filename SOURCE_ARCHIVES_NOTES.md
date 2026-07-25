# Source archival notes — Laguna derivation evidence (retrieved 2026-07-23)

Anchor for all "before/after" judgments:
**r0b0tlab/laguna-s-2.1-nvfp4-sm121-vllm created 2026-07-22T02:21:00Z; first
release v0.25.1-gb10-k7 published 2026-07-22T02:38:49Z; checkpoint-update
release 2026-07-23T00:53:06Z** (GitHub API, retrieved 2026-07-23).

## X posts — Wayback save FAILED (login wall); saved copies below (search-index text, retrieved 2026-07-23)

### @ivanfioravanti — https://x.com/ivanfioravanti/status/2079655857856434299
> "Laguna S 2.1 performance on a single DGX Spark. Prefill 600-800 tok/s decode
> is around 15 tok/s on prose and 22-24 on code. Without speculation, decode sits
> at 13-14 tok/s on every engine we tried on the GB10, which is the
> memory-bandwidth ceiling for this model."
Post date: not visible in index; corroborates the NVIDIA-forum numbers.

### @sudoingX — https://x.com/sudoingX/status/2066935217194250356
> "the results are in. two 128gb boxes on my desk, the nvidia dgx spark and the
> amd strix halo... ran them head to head on the exact same model..."
(Snapshot id 2066935217194250356 — Spark vs Strix Halo head-to-head.)

### @sudoingX — https://x.com/sudoingX/status/2050517565097824303
> "a week with the dgx spark, here is what is on it and what i have measured so
> far... nvidia gb10 sm_121, 124 gb unified lpddr5x at 273 gb/s, cuda 13.0..."

### @darvasch (DFlash 3x-on-code / slower-on-agent-reasoning claim)
**NOT LOCATED** by search on 2026-07-23. Claim survives only as the paraphrase
in COMMUNITY_RESEARCH.md. Treat as UNVERIFIED; do not cite publicly.

### @stevibe ("Spark 19.44, PRO6000 108, 4x5090 145")
**NOT LOCATED** by search on 2026-07-23. Treat as UNVERIFIED; do not cite
publicly. (Similar cross-hardware comparisons exist from other authors.)

## NVIDIA Developer Forums thread (Discourse JSON, retrieved 2026-07-23)

Thread: "Laguna S 2.1 Config & Benchmarks"
https://forums.developer.nvidia.com/t/laguna-s-2-1-config-benchmarks/377663
Created: **2026-07-21T18:32:17Z** (user serapis) — model-release-day thread.

Key dated receipts (all BEFORE r0b0tlab's 2026-07-22T02:21Z creation):
- **vr8vr8, 2026-07-21T18:57:30Z**: "go for num_speculative_tokens = 7. I
  managed to get speed around 40-50 tokens/s" ← K=7 is community-first.
- vr8vr8, 2026-07-21T19:14:18Z: c=2 + K=7 results on the eugr-derived recipe
  (bilikaz/spark-vllm-docker branch feat/laguna-s-2.1-nvfp4).
- clawdiusmaximus, 2026-07-21T22:17:23Z: with the HF card's 15 spec tokens,
  "draft acceptance was consistently 0-15%... 6-15 were always at 0.0" ←
  the reduce-K-below-15 insight, community-first.
- serapis (OP), 2026-07-21T18:32:17Z: DFlash acceptance ~8% on release config.

## Laguna S 2.1 model release date
Poolside released Laguna S 2.1 on **2026-07-21** (MarkTechPost coverage dated
2026-07-21; forum thread same day). The entire tuning conversation—including
r0b0tlab's repo—is release-week work.
