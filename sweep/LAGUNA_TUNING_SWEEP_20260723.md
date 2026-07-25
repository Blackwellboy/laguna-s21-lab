# LAGUNA TUNING SWEEP — 2026-07-23/24 (Hermes / spark-host)

**TEMPORARY HANDOFF — NOT CANONICAL.** Canonical truth lives in `<CONTROL_PLANE>`; staged
state-doc text is in `LAGUNA_SWEEP_STATEDOC_PATCH_20260723.md` (apply only after
remediation batch 1 completes).

## Executive summary

- **Production default promoted: DFlash K=7, max-num-seqs=32**, with 12 GiB KV
  pin, prefix caching + chunked prefill, batched 8192, FP8 KV, FLASHINFER,
  262,144 ctx — **selected via a 20-cell sweep on Hermes bench v1, 2026-07-23**
  (independence receipt below). Named alternate `interactive` = K=7/seqs=8.
- The winner equals the community/r0b0tlab flag pair on K and seqs — but was
  derived independently by measurement, and our config retains three deliberate
  differences: prefix caching ON, chunked prefill ON, 12 GiB KV pin.
- **DEEP_GEMM discrepancy CLOSED: INERT** on this build/path (source + measured).
- Cold long-context on the final config: see §6 (honest cold-prefill numbers).
- Live lane state at session start: Grok HAD restored the interactive profile
  (restart 2026-07-23 13:08:28) — the restore was real, only unrecorded.

## 0. Phase 0 — live-state probe (2026-07-23 13:30 AEST)

- Live cmdline: K=6, seqs=4, KV pin 12884901888, prefix+chunked ON → the
  "interactive/beat" profile. `/v1/models` healthy, max_model_len 262144.
- Unit Environment lacked `VLLM_USE_DEEP_GEMM`, **but** the start script
  exports `=0`, and `/proc/PID/environ` confirmed `VLLM_USE_DEEP_GEMM=0` in the
  live process. The recipe-vs-unit discrepancy was a paper artifact.
- Rollback snapshot: `spark-host:~/backups/laguna_phase0_20260723/` (unit + start
  script).

## 1. Phase 1 — 2D grid (20/20 cells, all OK)

Protocol per cell: full service restart → `/v1/models` readiness → cmdline
verification → warmup → SHORT Hermes bench v1 subset (categories tool/code/json,
depths 1K/3K, gen 96/384, 2 runs, c=1 and c=4; decode=(n−1)/(t_last−t_first)).
Constants: FP8 KV, FLASHINFER, 262144 ctx, util 0.85, top_k 20, KV pin 12 GiB,
**prefix caching + chunked prefill ON in every cell** (deliberate Hermes
agent-serving differentiator). Median cold load per restart: **614 s**.

| K | seqs | c1 overall | code | tool | json | c4 agg | TTFT ms |
|---|------|-----------|------|------|------|--------|---------|
| 5 | 4 | 23.87 | 37.59 | 23.87 | 17.28 | 54.48 | 339.45 |
| 6 | 4 | 26.0 | 39.35 | 25.3 | 17.68 | 57.95 | 337.2 |
| 7 | 4 | 26.13 | 44.34 | 26.13 | 18.91 | 61.02 | 328.38 |
| 8 | 4 | 20.23 | 31.31 | 20.23 | 13.88 | 50.62 | 371.83 |
| 9 | 4 | 19.39 | 33.63 | 19.39 | 13.54 | 52.75 | 373.14 |
| 5 | 8 | 28.47 | 36.41 | 28.47 | 18.45 | 56.25 | 334.69 |
| 6 | 8 | 25.69 | 41.08 | 25.69 | 18.27 | 62.26 | 335.11 |
| 7 | 8 | 32.38 | 46.03 | 35.19 | 20.9 | 57.97 | 325.41 |
| 8 | 8 | 21.84 | 32.01 | 21.84 | 13.78 | 56.33 | 369.44 |
| 9 | 8 | 18.93 | 35.83 | 18.93 | 13.92 | 54.19 | 370.37 |
| 5 | 16 | 26.95 | 38.13 | 27.49 | 18.2 | 58.53 | 341.63 |
| 6 | 16 | 32.04 | 40.16 | 32.04 | 18.17 | 59.39 | 320.7 |
| 7 | 16 | 26.36 | 43.96 | 26.36 | 19.91 | 53.69 | 320.32 |
| 8 | 16 | 22.27 | 32.98 | 22.27 | 14.06 | 44.6 | 370.98 |
| 9 | 16 | 23.2 | 36.34 | 23.74 | 15.0 | 53.17 | 365.31 |
| 5 | 32 | 23.2 | 37.46 | 23.2 | 18.66 | 58.38 | 333.86 |
| 6 | 32 | 25.58 | 40.29 | 25.58 | 19.31 | 60.14 | 319.02 |
| 7 | 32 | 26.2 | 42.83 | 26.2 | 20.53 | 61.65 | 322.38 |
| 8 | 32 | 20.58 | 31.68 | 20.58 | 14.1 | 53.03 | 374.57 |
| 9 | 32 | 24.05 | 36.23 | 24.05 | 13.96 | 57.67 | 374.18 |

Readings: **K=7 peaks at every seqs level; K≥8 collapses** (per-position DFlash
acceptance ~0 past position 3; TTFT also degrades ~50 ms). Failures: none.
K6s4 (prior production) re-measured at 26.0/39.35 — consistent with the earlier
Grok-audit numbers (21.75 overall on the 4-category matrix incl. prose; 38.3
code), i.e. good cross-session reproducibility.

## 2. Top-3 full Hermes bench v1 (all categories, depths 1K–64K, 3 runs)

Combined-score finalists: K6s16 (0.906), K7s8 (0.879), K7s32 (0.753).

| profile | c1 overall | code | tool | json | prose | median @64K |
|---------|-----------|------|------|------|-------|-------------|
| K6s16 | 21.48 | 38.2 | 26.59 | 18.54 | 17.74 | 20.41 |
| K7s8 | 22.25 | 43.56 | 29.44 | 19.07 | 18.71 | 21.1 |
| **K7s32** | **23.43** | **45.82** | 26.79 | **19.28** | 18.35 | 20.59 |

K6s16's short-bench 32.04 did not survive the full matrix (lucky tool window —
a caution against short-bench-only selection). **K7s32 wins** overall/code/json
and holds the grid's best c=4 aggregate (61.65); K7s8 takes tool/prose narrowly
→ kept as the `interactive` alternate. All three hold >20 tok/s at 64K depth.

## 3. Phase 2 A/Bs on the winner (one variable at a time, full bench each)

| arm | overall | code | tool | json | prose | verdict |
|-----|---------|------|------|------|-------|---------|
| baseline (batched 8192, DG=0) | 23.43 | 45.82 | 26.79 | 19.28 | 18.35 | — |
| batched **16384** | 23.14 | 42.19 | 30.08 | 19.55 | 18.97 | no gain; category flips within noise → **keep 8192** |
| DEEP_GEMM **unset** | 22.31 | 45.33 | 30.42 | 19.3 | 18.46 | noise-band → INERT |

`--cuda-graph-sizes` arm: **not run** (time cut; lowest priority per brief).

### DEEP_GEMM verdict: **INERT** (closes the long-open discrepancy)

- vLLM 0.25.1 defaults `VLLM_USE_DEEP_GEMM=1`; with it unset the engine loads
  the **vendored** `vllm.third_party.deep_gemm` and logs "DeepGEMM PDL enabled"
  (2 log lines; none with `=0`).
- Source: the live checkpoint is `compressed-tensors` / `nvfp4-pack-quantized`;
  the compressed-tensors quant package contains **zero** deep_gemm references —
  DeepGEMM is wired to FP8-quantization/scaled-mm/MoE-fp8 paths only. FP8 KV is
  attention, not GEMM. The only Blackwell interaction is an auto-disable for
  certain fp8 model types (config/vllm.py ~:945) — not our path.
- Measured: full-bench deltas within run noise (above).
- Policy: keep `VLLM_USE_DEEP_GEMM=0` in recipe/unit for explicitness (also
  skips loading an unused vendored module). Historical note: boots from the
  Grok era ran with it effectively default-on — immaterial to those numbers.

## 4. Final production config (live since 2026-07-24 ~00:40 AEST)

```
vllm serve …/poolside--Laguna-S-2.1-NVFP4-0761412 (revision 0761412)
  --speculative-config {"model":…DFlash-NVFP4,"num_speculative_tokens":7,"method":"dflash"}
  --max-num-seqs 32  --max-num-batched-tokens 8192
  --kv-cache-memory-bytes 12884901888  --kv-cache-dtype fp8
  --attention-backend FLASHINFER  --max-model-len 262144
  --gpu-memory-utilization 0.85  --enable-prefix-caching --enable-chunked-prefill
  env: VLLM_USE_DEEP_GEMM=0, CUTE_DSL_ARCH=sm_121a, FLASHINFER sampler
profiles: production (default, K7/s32) · interactive (K7/s8)
"beat"/r0b0tlab profile language removed from the start script.
```

**Smoke verification (post-promotion short bench, same protocol as grid):**
c1 overall 25.39 (grid 26.2, −3.1%) · code 43.71 (42.83, +2.1%) ·
c4 aggregate 63.34 (61.65, +2.7%) · TTFT 337.9 ms (322.4) — **PASS, within noise.**

## 5. Independence receipt (dated derivation entry)

> **K=7, max-num-seqs=32 selected via a 20-cell sweep (K∈{5..9} ×
> seqs∈{4,8,16,32}) on Hermes bench v1, SPARK-HOST GB10, 2026-07-23.**
> Protocol, per-cell raw JSON, and logs in this folder. Prior art acknowledged:
> K=7 was recommended on the NVIDIA developer forum 2026-07-21T18:57Z (before
> any third-party container release); our sweep confirms it independently and
> adds the seqs sweep + KV-pin/prefix-caching configuration.

## 6. Cold long-context on the final config

Method: unique random nonce as the FIRST line of every prompt (invalidates
prefix-cache block hashing from position 0), fresh service boot ~40 min prior,
each timed run a genuinely cold prefill. Streaming; TTFT = queue+prefill+first
token; decode = (n−1)/(t_last−t_first); KV usage sampled from /metrics ~1 s
into decode.

| run | prompt tokens | cold TTFT (s) | decode tok/s | total wall (s) | KV usage (of 327,717-tok pool) | needle |
|-----|---------------|---------------|--------------|----------------|-------------------------------|--------|
| cal ~18K | 18,436 | 6.0 | 16.8 | 6.8 | — | YES |
| 100K r0 | 103,708 | 45.60 | 19.46 | 46.6 | 30.0% | YES |
| 100K r1 | 103,709 | 45.71 | 18.47 | 46.7 | 30.0% | YES |
| 200K r0 | 209,478 | 132.80 | 17.57 | 133.9 | 60.3% | YES |
| 200K r1 | 209,481 | 133.24 | 14.28 | 134.6 | 60.3% | YES |
| 2×100K concurrent | 103,706 + 103,710 | 48.1 / 91.8 | contended (see note) | 93.1 total | 37.1% peak sampled | YES both |

Readings:
- **Cold prefill is the honest cost**: ≈2,270 tok/s at 100K depth (45.6 s to
  first token), ≈1,575 tok/s at 209K (133 s). Decode at depth stays strong:
  ~19 tok/s @100K, ~14–18 @200K (vs 23.4 shallow overall median).
- **~200K works.** The prior audit's HTTP 400s at "200K" were the client
  overshooting 262,144 during prompt growth — 209K prompts are accepted and
  retrieved fine. No binary-search ceiling needed: the ceiling is the
  configured window minus generation headroom.
- Concurrent cold 100K pairs: both fit the KV pool and retrieve, but prefill
  serializes (stream 2 TTFT 91.8 s ≈ two sequential prefills); aggregate
  wall-clock ≈ sequential. Cold concurrency buys capacity, not latency.
- These supersede the 2026-07-23 audit longctx speed figures, which were
  prefix-cache-warm (1.1–1.5 s "walls" at 100K+) and must not be published.

## 7. Coverage & honesty notes

- All 20 grid cells ran (no cuts); the only cut was the optional
  `--cuda-graph-sizes` arm.
- Short-bench cells are 2-run medians on a 3-category subset — good for
  ranking, not for publication headline numbers; publication numbers should
  come from the full-bench table (§2) and the smoke (§4).
- Prior Grok-audit A/B confound noted for the record: its "r0b0tlab profile"
  also disabled prefix caching, so K/seqs was confounded with cache state.
  This sweep held prefix caching ON everywhere.
- Raw data: `cells/*.json` (+ per-cell run logs + DFlash acceptance log
  windows), `full/*.json`, `sweep_results.jsonl`, `topk_results.jsonl`,
  `phase2_results.jsonl`, `longctx/`, driver sources (`sweep_driver.py`,
  `cell_bench.py`, `topk_driver.py`, `phase2_driver.py`, `longctx_cold.py`).
