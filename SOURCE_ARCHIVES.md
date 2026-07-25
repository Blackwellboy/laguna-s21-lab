# SOURCE ARCHIVES — Laguna derivation evidence (captured 2026-07-23 AEST)

**Anchor: r0b0tlab/laguna-s-2.1-nvfp4-sm121-vllm — repo created 2026-07-22T02:21:00Z,
first release v0.25.1-gb10-k7 2026-07-22T02:38:49Z, checkpoint update 2026-07-23T00:53:06Z
(GitHub API, retrieved 2026-07-23).** "BEFORE/AFTER/SAME-DAY" below is relative to 02:21Z.

| # | Source | Original URL | Archive | Pub date | vs r0b0tlab |
|---|--------|--------------|---------|----------|-------------|
| 1 | howtospark Laguna-XS recipe (k=6 sweep, seqs=2, 12GiB pin methodology) | howtospark.com/recipes/laguna-xs-2-1-nvfp4 | [web.archive.org/web/20260723074505](https://web.archive.org/web/20260723074505/https://howtospark.com/recipes/laguna-xs-2-1-nvfp4) | undated on page (cites vLLM PR merged 2026-07-03) | methodology predates; **page date unproven** |
| 2 | howtospark Laguna-S ×1 NVFP4 DFlash k=6 bench (42.9 tok/s) | howtospark.com/benchmarks/laguna-s-2-1--dgx-spark-x1--vllm--nvfp4--dflash-nvfp4-k6--p2048-o256-c1--2026-07-22 | [web/20260723074543](https://web.archive.org/web/20260723074543/https://howtospark.com/benchmarks/laguna-s-2-1--dgx-spark-x1--vllm--nvfp4--dflash-nvfp4-k6--p2048-o256-c1--2026-07-22) | 2026-07-22 (day only) | **SAME-DAY — order unprovable** |
| 3 | howtospark Laguna-S ×1 NVFP4 no-draft bench (18.9 tok/s) | …--no-draft--p2048-o256-c1--2026-07-22 | [web/20260723074625](https://web.archive.org/web/20260723074625/https://howtospark.com/benchmarks/laguna-s-2-1--dgx-spark-x1--vllm--nvfp4--no-draft--p2048-o256-c1--2026-07-22) | 2026-07-22 (day only) | SAME-DAY |
| 4 | MiaAI-Lab Laguna-S serving stack (docker, FlashInfer nightly, seqs=4/K=7) | github.com/MiaAI-Lab/Laguna-S-2.1-DGX-Spark-RTX-6000-PRO | [web/20260723074745](https://web.archive.org/web/20260723074745/https://github.com/MiaAI-Lab/Laguna-S-2.1-DGX-Spark-RTX-6000-PRO) | created **2026-07-21T19:07:51Z** | **BEFORE (−7h14m)** |
| 5 | eugr/spark-vllm-docker (community Spark vLLM base) | github.com/eugr/spark-vllm-docker | [web/20260723074902](https://web.archive.org/web/20260723074902/https://github.com/eugr/spark-vllm-docker) | created **2025-11-25** | **BEFORE (months)** |
| 6 | NVIDIA forum "Laguna S 2.1 Config & Benchmarks" (K=7 rec; seqs-32-for-DFlash; acceptance data) | forums.developer.nvidia.com/t/laguna-s-2-1-config-benchmarks/377663 | [web/20260723075033](https://web.archive.org/web/20260723075033/https://forums.developer.nvidia.com/t/laguna-s-2-1-config-benchmarks/377663) | opened **2026-07-21T18:32Z**; vr8vr8 K=7 post **2026-07-21T18:57:30Z** | **BEFORE (−7h24m)** — strongest receipt |
| 7 | Poolside HF card (base recipe, K=15 default, parsers, arch env) | huggingface.co/poolside/Laguna-S-2.1-NVFP4 | [web/20260723075152](https://web.archive.org/web/20260723075152/https://huggingface.co/poolside/Laguna-S-2.1-NVFP4) | model release 2026-07-21 | BEFORE |
| 8 | r0b0tlab repo (diff baseline) | github.com/r0b0tlab/laguna-s-2.1-nvfp4-sm121-vllm | **SPN FAILED ×2** — record = local file corpus `originality/raw/r0b0tlab/` (retrieved 2026-07-23) + GitHub API metadata; retry archive later | created 2026-07-22T02:21Z | — |
| 9 | MarkTechPost: Poolside releases Laguna S 2.1 | marktechpost.com/2026/07/21/poolside-releases-laguna-s-2-1/ | [web/20260723075350](https://web.archive.org/web/20260723075350/https://www.marktechpost.com/2026/07/21/poolside-releases-laguna-s-2-1/) | 2026-07-21 | BEFORE (release-date evidence) |
| 10 | @ivanfioravanti Laguna-S Spark numbers | x.com/ivanfioravanti/status/2079655857856434299 | **SPN blocked (login wall)** — saved quote in SOURCE_ARCHIVES_NOTES.md, retrieved 2026-07-23 | undated in index | corroboration only |
| 11 | @sudoingX Spark posts ×2 | x.com/sudoingX/status/2066935217194250356 · …/2050517565097824303 | SPN blocked — saved quotes in NOTES, retrieved 2026-07-23 | id-2050… ≈ pre-Jul | BEFORE (older post) |
| 12 | @darvasch DFlash-selective claim | not located | **UNVERIFIED — do not cite** | — | — |
| 13 | @stevibe cross-hardware numbers | not located | **UNVERIFIED — do not cite** | — | — |

## Derivation-story implications (honest read)

**Strong receipts (predate r0b0tlab by hours-to-months):** K=7 recommendation
(forum, 2026-07-21T18:57Z), reduce-K-below-15 acceptance analysis (forum,
2026-07-21T22:17Z), MiaAI-Lab full serving stack (2026-07-21T19:07Z), eugr base
(2025-11), Poolside HF card (2026-07-21).

**Weak/flagged items:**
- howtospark **Laguna-S** k=6 benchmark pages are dated 2026-07-22 (day
  resolution) — same calendar day as r0b0tlab's 02:21Z creation; before/after
  is unprovable. The k=6 *methodology* page is for Laguna-**XS** (sibling
  model) and is undated.
- ORIGINALITY_AUDIT.md's claim "max-num-seqs=4 (+6–7% vs 2) from howtospark"
  could not be located on the archived pages (the XS recipe recommends seqs=2).
  The seqs=4 attribution should be corrected to MiaAI-Lab's start.sh (seqs=4,
  repo predates r0b0tlab) before publication.
- The two unlocated X posts must drop out of any public claim set.
