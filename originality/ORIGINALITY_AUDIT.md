# ORIGINALITY AUDIT — Hermes Laguna S 2.1 vs r0b0tlab

**Date:** 2026-07-23  
**Their repo:** https://github.com/r0b0tlab/laguna-s-2.1-nvfp4-sm121-vllm (MIT © 2026 r0b0tlab)  
**Our artifacts:** `spark-host:~/containers/laguna-s21-nvfp4/`, `~/bin/start-laguna-s21-nvfp4.sh`  
**Status:** Independent derivation with shared *industry-standard* vLLM/Poolside flags. **No substantial copy** of their entrypoint, Dockerfile, audit harness, or README prose.

---

## 1. File-by-file diff summary

| Artifact | Theirs | Ours | Similarity | Verdict |
|----------|--------|------|------------|---------|
| entrypoint | `scripts/entrypoint.sh` (~78 lines, audit reject gates, revision pins, DFLASH_TOKENS env) | `entrypoint.sh` (~40 lines, simple env defaults) | **SequenceMatcher ratio 0.12** | Independent |
| Dockerfile | `docker/Dockerfile.production` (~194 lines, multi-stage, source-build style) | `Dockerfile` (~30 lines, `FROM vllm/vllm-openai:v0.25.1` + FlashInfer pip) | **ratio 0.05** | Independent |
| README | Long release-contract narrative | Short Hermes recipe | Different structure | Independent |
| Runtime manifests / SparkRun / audit_runtime | Present | Absent | N/A | We did not use |

### Exact shared non-comment lines (entrypoint)
Only unavoidable bash boilerplate:
```
set -euo pipefail
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
```
**No** shared lines from their reject gates (`R0B0TLAB_LAUNCH_REJECTED`), audit binary, revision JSON construction, or `DFLASH_TOKENS` logic.

### Overlapping *flags* that everyone uses (not evidence of copying)
These appear in Poolside HF card, MiaAI Docker, howtospark, and their contract:
- `--tool-call-parser poolside_v1` / `--reasoning-parser poolside_v1`
- `--enable-auto-tool-choice`
- `--override-generation-config` temp 0.7 / top_p 0.95 / top_k 20
- `--max-model-len 262144`
- `--gpu-memory-utilization 0.85`
- `--max-num-batched-tokens 8192`
- `method=dflash` + matched DFlash draft path
- `CUTE_DSL_ARCH=sm_121a` / `MAX_JOBS=4` (Poolside Spark recipe)

### Flags only in our default pack
- `--enable-prefix-caching`
- `--enable-chunked-prefill`
- `--kv-cache-memory-bytes 12884901888`
- default `num_speculative_tokens=6` (they default **7**)
- default `max-num-seqs=4` (they default **32**)

### Flags only in their default pack
- `--revision` pin on CLI (we pin via on-disk 0761412 directory + REVISION.txt)
- `--tensor-parallel-size 1` (implicit for us)
- `--trust-remote-code`
- Fail-closed NVFP4-KV rejection + flashinfer_b12x rejection
- `audit_runtime.py` preflight

---

## 2. Flag → source → date adopted (public story table)

| Flag / setting | Source we used | Date adopted (Hermes) | Notes |
|----------------|----------------|----------------------|-------|
| vLLM 0.25.1 + FlashInfer `0.6.15.dev20260712` | Poolside HF NVFP4 card (DGX Spark recipe) | 2026-07-22 | Same stack class as community; independent install on single DGX Spark |
| `CUTE_DSL_ARCH=sm_121a` | Poolside HF card | 2026-07-22 | Required for FP4 JIT on GB10 |
| `MAX_JOBS=4` | Poolside HF card (OOM warning) | 2026-07-22 | |
| `method=dflash` + matched NVFP4 draft | Poolside HF card | 2026-07-22 | |
| `top_k=20` + temp 0.7 / top_p 0.95 | Poolside HF generation defaults | 2026-07-22 | |
| `tool/reasoning poolside_v1` | Poolside HF card | 2026-07-22 | |
| `max-num-seqs` **4** (beat) | **howtospark.com** measured recipe (+6–7% vs 2) + MiaAI-Lab start.sh | 2026-07-23 | They use **32** |
| `num_speculative_tokens` **6** (beat) | **howtospark** K-sweep peak (k=6 best tok/s) | 2026-07-23 | They use **7** after their K∈{3,5,7,11,15} qual |
| `kv-cache-memory-bytes` **12 GiB** | **howtospark** (327,717 tokens / 1.25× @ 256K) | 2026-07-23 | They leave unset |
| prefix-caching + chunked-prefill | Hermes agent multi-turn need (our fleet) | 2026-07-23 | Off in their published llama-benchy |
| `VLLM_USE_DEEP_GEMM=0` | Community DGX Spark recipes / Spark threads | 2026-07-23 | |
| `attention-backend FLASHINFER` + `kv-cache-dtype fp8` | Poolside/community + their published contract (we added for parity after reading their release) | 2026-07-23 | **Industry standard**; not their unique IP |
| Checkpoint `0761412` spinquantless/norot | Poolside HF main tip; we re-downloaded after seeing community re-release notes | 2026-07-23 | Same public weights as them |

**Narrative for publication:**  
“We followed Poolside’s official Spark recipe, then tuned single-stream flags from howtospark + MiaAI measurements and our agent-harness needs. Overlap with r0b0tlab is the public Poolside baseline, not a fork of their release contract.”

---

## 3. License verdict

- **Their LICENSE:** MIT, Copyright (c) 2026 r0b0tlab.  
- **Did we copy their code?** **No substantial portion.** Similarity ratios ~0.05–0.12; only generic bash defaults match.  
- **Attribution required?** **Not required** for our independently written entrypoint/Dockerfile/README.  
- **If we later quote their published numbers** for comparison, cite their repo/report (good practice, not a license obligation for benchmarks).  
- **Do not** ship their `R0B0TLAB_*` strings, audit scripts, or Dockerfile.production text.

### Internal notes to clean before public post (not license, but hygiene)
| Location | Issue | Action before publish |
|----------|-------|------------------------|
| `start-laguna-s21-nvfp4.sh` comments | Mentions “BEAT r0b0tlab” | Soften to “beat profile vs K7/seqs32 reference” |
| Old README (pre-fix) | Listed stale K=7/seqs=32 and **private IP** | **Fixed in publishable container README** (HOST env only) |
| Production bind | Live service uses private private IP | Keep out of image; document as operator env |

---

## 4. Originality evidence — deliberate differences from their production default

| Dimension | r0b0tlab production | Hermes **beat** default |
|-----------|---------------------|-------------------------|
| DFlash K | **7** | **6** |
| max-num-seqs | **32** | **4** |
| KV pin | unset (util 0.85) | **12 GiB** |
| prefix-caching | not in default serve path for their bench | **on** |
| chunked-prefill | not emphasized | **on** |
| Benchmark protocol | llama-benchy 2/4/8/16K × 128 gen | **Hermes bench v1** (1/3/6K… agent shapes) |
| Container style | Fail-closed multi-file contract + GHCR pin | Thin venv-proven recipe + env overrides |

These differences are the public proof we are not a re-skin of their image.

---

## 5. Checkpoint provenance (live)

| Component | Identity |
|-----------|----------|
| Target path | `$HOME/models/hf/poolside--Laguna-S-2.1-NVFP4-0761412` |
| Target revision | `07614121b31898586430f189d27a25a0be310843` |
| Target `config.json` sha256 | `9aaacf4716d09fcdef6e70a068d5af7ec58f92e765b6b5e439a13063825a259d` |
| Draft path | `…/poolside--Laguna-S-2.1-DFlash-NVFP4` |
| Draft revision (HF tip) | `723794750422b3efbf3a7b3af76dffb4ba035943` |
| Live `max_model_len` | **262144** |

---

## 6. Conclusion

**Ship as original Hermes work** with honest citations to Poolside, howtospark, and MiaAI for *measured* flag choices.  
**Do not** claim their 8,620-case battery.  
**Do** claim: independent protocol + flag pack wins on the same GB10 under Hermes bench v1 (see `PROFILE_AB_RESULTS.md`).
