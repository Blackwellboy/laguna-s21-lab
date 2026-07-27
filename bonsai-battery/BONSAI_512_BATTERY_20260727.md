# Bonsai 27B at the quant floor: 1-bit fork vs 2-bit ternary, 512-case blinded battery

**MLX on Apple silicon, 2026-07-23 run, aggregates published 2026-07-27.**

## What this is

A frozen, hashed, blinded 512-case hostile evaluation comparing two low-bit builds
of the same 27B model (Bonsai 27B) on the same 32GB Apple-silicon desktop:

- **Arm A: ternary 2-bit** on the production MLX runtime. This build runs
  always-on watchdog/triage (sentinel) duty in daily use.
- **Arm B: 1-bit** on a patched PrismML MLX fork
  (`github.com/PrismML-Eng/mlx`, tag `v0.0.1-prism`, base mlx 0.31.2); stock mlx
  rejects `bits=1` outright.

Identical prompts, identical mechanical scoring rules, both arms scored blind,
no model judged itself. 13 groups, 512 cases per arm (seed 20260723), plus a
10x-repeat variance battery (60 items per arm), a solo performance matrix, and
a runtime-robustness pass.

## Headline

| | ternary 2-bit (A) | 1-bit fork (B) |
|---|---|---|
| overall pass | **345/512 (67.4%)** | **337/512 (65.8%)** |
| decode tok/s, 256-token generation, p50 | 13.52 | **26.94** |
| RSS after load | 7,866,480 KB (7.50 GiB) | **4,509,440 KB (4.30 GiB)** |

The 1-bit build reaches rough intelligence parity (8 cases behind on 512, with
legible per-group structure rather than uniform decay) at 2.0x decode speed and
42.7% less resident memory. Scoring is deliberately strict and applied equally,
so the comparison should be read on the A-vs-B delta, not the absolute rates.

## Per-group scorecard

| group | A pass/total | B pass/total | B-A rate delta |
|---|---|---|---|
| adversarial | 33/40 | 34/40 | +0.025 |
| coding | 29/29 | 26/29 | -0.103 |
| format | 49/50 | 49/50 | 0 |
| long-context (in-harness) | 3/4 | 2/4 | -0.25 |
| long-horizon | 10/15 | 8/15 | -0.133 |
| multi-turn | 10/12 | 11/12 | +0.083 |
| operational | 22/50 | 15/50 | -0.14 |
| over-gating | 36/50 | 37/50 | +0.02 |
| poisoned-context | 18/40 | 22/40 | +0.10 |
| severity triage | 47/100 | 49/100 | +0.02 |
| tool-call | 29/40 | 32/40 | +0.075 |
| truthfulness | 39/52 | 34/52 | -0.096 |
| social-post discipline | 20/30 | 18/30 | -0.067 |
| **total** | **345/512** | **337/512** | **-0.016** |

The tradeoff is legible: 1-bit gives up coding, truthfulness, long-horizon and
operational points, and gains on poisoned-context resistance, multi-turn and
tool-call validity. Low absolute rates on operational/severity/poisoned groups
are by design; the suite is hostile and graded mechanically with no partial
credit.

Harness limitation, stated plainly: 8 tool-sequencing cases per arm ended in a
runner-side KeyError and are counted as non-passes. The defect is exactly
symmetric (same 8 case IDs, both arms), so it deflates both absolute tool-call
rates equally and does not move the delta.

## Safety-critical flags (count, A vs B; lower is better; equal-or-better gates all passed)

| flag | A | B |
|---|---|---|
| critical false-negatives | 3 | 3 |
| fabricated live metrics | 2 | 2 |
| fabricated command success | 8 | 8 |
| false-memory accepted | 13 | 11 |
| hallucinated tool success | 0 | 0 |
| false escalations | 23 | 21 |

Every mandatory not-worse-than-production quality gate passed except the 64k
behavioural gate (below). All runtime gates passed (zero crashes, zero orphan
processes, zero duplicate listeners, restart recovery clean).

## Variance (10x repeat battery, 60 items per arm)

- Severity-triage wobble: 0.0 both arms (fully stable labels across repeats).
- Mean answer deviation: A 0.007, B 0.010. One A item and two B items showed
  any deviation at all; everything else was 10/10 identical in substance.

Low-bit quantization did not buy run-to-run instability on this workload.

## Performance matrix (solo, same box, no other load)

| decode length | A tok/s p50 | B tok/s p50 |
|---|---|---|
| 16 | 19.33 | 32.21 |
| 64 | 16.41 | 28.28 |
| 256 | 13.52 | 26.94 |
| 1024 | 13.23 | 25.69 |

Warm TTFT p50 at the 64-token cell: A 0.453 s vs B 0.299 s. The speed ratio
holds at roughly 2x across the ladder. Full ladders, prefill estimates,
concurrency levels, RSS-by-context and thermal/swap readings are in
`PERFORMANCE_RESULTS.json` in this folder.

## Runtime robustness (fresh dedicated server per arm)

From `RUNTIME_ROBUSTNESS_RESULTS.json`: 1-bit clean start 6.1 s, 100-request
sequence with 0 errors, mixed-concurrency clean, survived 10 malformed requests
alive, prompt-cache cold 7.56 s vs warm 0.99 s. Fresh 32k-context requests
complete on both arms (about 570 s wall). At 64k the arms diverge: the 1-bit
fork completed (1,305 s, correct completion marker), the ternary production
runtime dropped the connection.

## The 64k shared-environment failure (open lead, documented on purpose)

Inside the shared battery harness (both 27B builds resident on one 32GB box,
alternating requests), the 64k long-context case ended in a dropped connection
on BOTH arms. On fresh dedicated servers, the same 64k request completed on the
1-bit fork and still failed on ternary. So the in-harness 64k failure is an
environment effect (memory pressure on a shared box is the working suspicion;
the MLX Metal buffer cache is known to grow under sustained load and the 1-bit
runtime required an explicit cache cap for exactly that reason), while the
ternary 64k failure reproduced even fresh and remains unexplained. The 64k
behavioural gate is recorded as FAIL and this is the one open gate. Treat both
findings as leads, not settled conclusions: long-context verdicts taken inside
shared-environment harnesses can be artifacts of the harness.

## The patch story: what it took to run 1-bit at all

The 1-bit weights require the PrismML fork, and the build box has Command Line
Tools only (no full Xcode/Metal toolchain). Five deterministic build patches
made the fork compile and serve:

1. Hardcode `MLX_METAL_VERSION` in CMakeLists.txt (the stock probe shells out
   to `xcrun metal`, which does not exist without the Metal toolchain).
2. Build with `-DMLX_METAL_JIT=ON` so Metal kernels compile just-in-time
   through the OS Metal framework instead of ahead-of-time via the missing CLIs.
3. Replace the `metallib` link step with a copy of the prebuilt `mlx.metallib`
   extracted from the stock `mlx-metal==0.31.2` wheel. Safe because the fork's
   kernel diffs are all in the JIT-compiled set.
4. Pin the JIT language to Metal 3.2 (the OS defaults to Metal 4.0, which
   rejects the fork's pre-4.0 kernels with bf16/vector errors).
5. Replace the `xcrun`-dependent JIT-preamble script with a Python include-DFS
   (the original silently emitted broken preambles without the metal CLI).

Plus two operational requirements: `mlx-lm` pinned at 0.31.2 with `--no-deps`
(0.31.3 needs the mlx 0.32 API and a bare upgrade clobbers the fork), and a
mandatory MLX cache limit at launch to stop unbounded Metal-cache growth from
swap-thrashing a shared desktop during long-lived serving.

Reproducibility was verified by re-applying all five patches to a fresh clone:
deterministic, no reboot required, first load pays an ~11 minute JIT compile
that is cached afterwards (reloads 1-2 min). Verdict from the run record:
REPRODUCIBLE but FRAGILE. Any mlx/mlx-lm upgrade breaks it; acceptable for a
pinned appliance, needs the patch set version-controlled before production
reliance.

## Decision reached (and what did not happen)

Recorded decision: **ONE_BIT_READY_FOR_EXTENDED_CANARY**. The 1-bit build met
every equal-or-better safety gate, holds parity-class quality at 2x speed and
43% less RAM, and regresses where it regresses in plain sight. Production was
restored to the ternary build after testing; no flip was performed and none is
implied by this document.

## Scope

These numbers describe exactly one pairing: this Bonsai 27B ternary 2-bit MLX
production build vs this 1-bit PrismML-fork build, on one 32GB Apple-silicon
desktop shared with a live user session, one frozen 512-case suite, one seed
batch, mechanical scoring. They are not general claims about ternary vs 1-bit
quantization, other models, other MLX versions, or other hardware.

## What is published here, and what is not

Published: this summary, `SCORE_AGG.json` (per-group counts and flag tallies),
`PERFORMANCE_RESULTS.json` (full solo performance matrix),
`RUNTIME_ROBUSTNESS_RESULTS.json` (robustness pass), and `FILE_HASHES.jsonl`
(SHA256 over the published copies, regenerated for this folder).

Withheld: the 512 prompt corpus, answer keys, per-item raw runs and variance
transcripts. The prompts embed realistic operational scenarios modeled on the
operator's own infrastructure and are a topology disclosure even after token
scrubbing; the private-corpus precedent from our earlier retrieval benchmark
applies. Aggregates here were re-derived directly from the per-item raw before
publication (recount reproduced the frozen scorecard exactly: 345/512 and
337/512, all 13 groups matching).
