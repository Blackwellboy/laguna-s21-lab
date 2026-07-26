# 0xSero Laguna S 2.1 Hybrid 3.25bpw vs our published NVFP4 — quant-floor verification, 2026-07-27


## Compatibility gate (PASSED — this was the go/no-go)
- Repo `0xSero/Laguna-S-2.1-Hybrid-3.25bpw` @ `ecd9d39b` (2026-07-25). Format: two-tier expert quant — 64 hot experts/layer kept byte-exact NVFP4 + 192 tail experts/layer EXL3 Trellis-3 (18,086 files: compacted 14-shard base + per-expert tail safetensors + tier-map + provenance manifests, 49 GiB on disk).
- Ships its own serving stack: `runtime/Dockerfile` FROM `ghcr.io/anemll/dspark-vllm-gx10:0.1.1` (DGX Spark arm64 image) + vendored exllamav3 @ `c5d9c657` (tarball SHA256 verified = Dockerfile pin) + `patch_exllamav3_arm64.py` + pinned flashinfer 0.6.13 + 34KB `sitecustomize.py` overlay. TORCH_CUDA_ARCH_LIST=12.1a / CUTE_DSL_ARCH=sm_121a — **explicitly targets GB10**. Built first try on spark-host-3 (image `laguna-vllm-hybrid:20260725-a10-tp1`, sha256 `19518f6b…`).
- Launched via the repo's own single-Spark recipe (TR3 tier, gmu 0.86, ctx 200000, max-num-seqs 4, moe-backend flashinfer_cutlass, TRITON_ATTN, temp 0.7/top_p 0.95 default): container `laguna_hybrid_test` on spark-host-3 :8101. Served and produced coherent output first launch (17·19=323; clean technical prose).

## Memory footprint (measured)
- Package on disk: 49 GiB. Host during serve: 114/121 GiB used at gmu 0.86 (weights + 200K-ctx KV pool in unified memory). Fits one Spark with room; the "56GB class" claim refers to the weight package, which holds.

## Quality — canonical 16-task intel suite (identical harness/grading, thinking off, 3 runs)
| model | score |
|---|---|
| Laguna NVFP4 + DFlash (banked 2026-07-23) | 15/16 |
| **Hybrid 3.25bpw (plain decode)** | **15/16 majority** (14/15/14) |

**Quant floor:** the hybrid's single *stable* miss is `logic_liar` (answers A instead of B, 3/3 runs) — one logic-puzzle regression vs the full-precision run pattern; math 3/3, coding, structured, instruction, systems all hold. Occasional flaky misses (`debug_dflash` 1/3, `agent_plan` 1/3) within normal wobble. On this suite, 3.25bpw costs Laguna essentially one reasoning cell, not general capability.

## Speed — hermes_bench_v1 quick (1K/3K/6K, thinking off, temp 0), NO speculative decoding
| metric | Hybrid 3.25bpw (plain) | Published NVFP4 (+DFlash K=7) |
|---|---|---|
| tool / code / json / prose (c=1 median) | 15.1 / 15.0 / 15.1 / 15.1 | 26.8 / 45.8 / 19.3 / 18.4 |
| overall c=1 | **15.1** (dead flat, all categories/depths) | 23.4 |
| TTFT @1K | ~220 ms | ~330 ms |
| c=4 aggregate | **46.5 median / 54.8 max** | 61.7 |
- **This is quant-vs-quant WITHOUT spec decode on the hybrid side** (no DFlash draft exists for the hybrid; runtime exposes no speculative mode we could enable — none reported). The published NVFP4 numbers include DFlash; its uplift is largest on code (45.8), which is why the code gap looks dramatic. The flat 15.1 profile is the hybrid's raw dense-decode rate on GB10.
- 0xSero's published claim "58.20 aggregate tok/s @ c4" is **plausible**: we measured 54.8 max / 46.5 median on Hermes-shaped prompts.

## Verdict
- **The 3.25bpw hybrid is REAL and works on GB10 out of the box** — cleanest third-party container recipe we've tested (pinned hashes, arm64 patch, first-try build+serve).
- **Quality floor: ~intact.** 15/16 majority on our suite; measurable damage isolated to one logic cell (logic_liar stable-wrong).
- **Speed: plain 15.1 tok/s c=1** — about 65% of our DFlash-accelerated overall median (23.4) and ~1/3 of DFlash code speed. Without a draft model it cannot compete on code emission; its win is fitting the full 256-expert model + 200K ctx in ~49 GiB weights with quality nearly intact — the interesting use is dual-model-per-Spark or Spark+headroom scenarios.
- Terminal-bench "~60% pace" community claim: not testable on our harness; not evaluated.

## Evidence
- `intel16_hybrid325.json`, `bench_hybrid/results/…laguna_hybrid325_tr3_noSpec_spark-host-3…json` + run log (this folder)
- Build: spark-host-3 `<workspace>/hybrid_build/` (dereferenced runtime context), image `laguna-vllm-hybrid:20260725-a10-tp1`
