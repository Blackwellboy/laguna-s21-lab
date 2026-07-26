# Qwen 3.6 35B-A3B vs Laguna S 2.1 — head-to-head on identical harnesses, 2026-07-27

First single-suite head-to-head behind the community claim "Qwen 3.6 35B-A3B beats Laguna."

## Setups (both 1× GB10 DGX Spark, same harnesses)
| | Qwen (measured this session) | Laguna (published/banked, NOT re-measured) |
|---|---|---|
| Model | `nvidia/Qwen3.6-35B-A3B-NVFP4` @ `491c2f1e` (35B MoE, 3B active, NVFP4) | `poolside/Laguna-S-2.1-NVFP4` @ `0761412` + DFlash draft |
| Host | spark-host-2 :8100, vllm/vllm-openai:nightly (2026-06-21), docker `qwen35b_test` | spark-host-1 :8000 (not re-served this session; numbers from Blackwellboy/laguna-s21-lab + banked evidence) |
| Serve | model-card DGX Spark command verbatim: FLASHINFER attn, MARLIN NvFp4 MoE, fp8 KV, MTP spec n=3, gmu 0.4, ctx 262144, max-num-seqs 4 | production K=7/s32 profile, FLASHINFER CUTLASS, fp8 KV, ctx 262144 |
| Sampling | model generation_config: temp 1.0 / top_p 0.95 / top_k 20 (arms); harness-forced temp 0 (speed + intel), documented per cell | published protocol (thinking off, temp 0) |
| Memory | `free` on spark-host-2 during serve: ~81 GiB used total (gmu 0.4 cap; 121 GiB box) | ~70 GiB class + draft (see public repo) |

## Speed — hermes_bench_v1 FULL protocol (identical harness, thinking off, temp 0)
| metric (c=1 median decode tok/s) | Qwen 35B-A3B | Laguna NVFP4+DFlash | winner |
|---|---|---|---|
| tool | **126.8** | 26.8 | Qwen ~4.7× |
| code | **104.0** | 45.8 | Qwen ~2.3× |
| json/structured | **98.6** | 19.3 | Qwen ~5.1× |
| prose floor | **82.5** | 18.4 | Qwen ~4.5× |
| overall median c=1 | **99.4** | 23.4 | Qwen ~4.2× |
| by depth 1K/3K/6K/24K/64K | 101 / 105 / 106 / 97.5 / **93.6** | >20 @64K | Qwen |
| TTFT @1K | ~268 ms | ~330 ms | Qwen |
| TTFT @64K | **~1.5 s** | (cold 100K: 45.6 s) | Qwen (GDN hybrid-linear attention prefill) |
| c=4 aggregate | **165 median / 256 max** | 61.7 | Qwen |

Conditions: Qwen numbers include MTP n=3 acceptance; 236-row protocol, 3 runs/cell, streaming decode (n−1)/(t_last−t_first). Laguna numbers are the published K7/s32 full-bench medians. Laguna TTFT@64K not published; the 100K cold figure is the nearest published anchor and is not directly comparable (different depth + cold cache) — flagged, not scored.

## Intelligence — canonical 16-task suite (identical prompts + grading as the 2026-07-23 triple compare)
| arm | score | notes |
|---|---|---|
| Laguna (banked 2026-07-23, thinking off, stock budgets) | **15/16** | misses 1 (historical run; baseline AND after) |
| Qwen thinking OFF, stock budgets (protocol-identical) | **11/16** (11/11/11, 3 runs) | fails ALL math (17*19+23*7→432!) + both logic tasks — the 3B-active floor without thinking |
| Qwen thinking ON, stock budgets | 1/16 | artifact: 350/800-token caps consumed by thinking → empty content. Reported for transparency, not a quality claim |
| Qwen thinking ON, mt=4000 (documented deviation) | **15/16 majority** (16/14/15) | matches Laguna — but needs ~13.4 s/task median vs 0.7 s/task thinking-off; only stable miss = agent_plan formatting |

**Reading:** Qwen only reaches Laguna-class correctness by spending thinking tokens (~19× task latency on this suite). Laguna delivers 15/16 reflexively.

## Arm A — agentic/multi-turn (tool-calling loop, 3 scenarios × 3 runs, model-default sampling)
Qwen: **33/36 (91.7%)** — tool selection 9/9, JSON args 9/9, final-answer misses 3 (verbosity/format drift on synthesis turns). Native `tools` + `qwen3_xml` parser worked first try. Laguna comparison: no published same-protocol number; Laguna's agentic evidence is the 12 h soak (tool tasks, 2 personas, zero incidents) — qualitative, not scored here.

## Arm B — single-shot generation (the community's Qwen-wins shape, model-default sampling, thinking on)
| cell | Qwen (3 runs) | Laguna |
|---|---|---|
| Tetris one-shot (single HTML, canvas, 7 pieces, rotate/clear/score/game-over) | **3/3 PASS** — JS parses, all feature checks, 3.6–5.4K tokens in **31–48 s wall** | N/A (no published cell; not re-served this session) |
| Snake (curses, single file) | 3/3 PASS (py_compile + features) | N/A |
| CLI todo app (argparse + JSON persistence) | 3/3 PASS incl. live add/list smoke test | N/A |
Observed decode during arm B: 118–310 tok/s (MTP thrives on code).

## Verdict / routing conclusion
- **Single-shot generation and raw speed: Qwen 3.6 35B-A3B clearly wins on this hardware** — ~4× decode, ~2.7× c=4 aggregate, near-flat decode to 64K, and it one-shots Tetris-class tasks in under a minute. The community claim is CONFIRMED for this shape.
- **Reflexive (thinking-off) correctness: Laguna clearly wins** (15/16 vs 11/16); Qwen's math/logic collapses without thinking. With thinking Qwen ties at 15/16 but pays ~19× latency per task, eroding much of its speed advantage on short reasoning-bound turns.
- **Agentic multi-turn: both competent.** Qwen 91.7% on our scored loop with excellent native tool-calling; Laguna's soak evidence remains the deeper agentic proof. No same-protocol loser here — thesis "Laguna wins agentic" is NOT confirmed but NOT refuted (Laguna unmeasurable this session).
- **Routing suggestion:** Qwen 35B-A3B is the better *bulk generation / code-emission / high-throughput* single-Spark lane; Laguna remains the better *reflexive reasoning / verifier-adjacent* lane. They are complementary, not substitutes.

## Evidence
- Speed: `bench_qwen/results/hermes_bench_v1_qwen35b_a3b_nvfp4_mtp3_spark-host-2_*.json` (+ run log)
- Intel: `intel16_qwen35b.json`, `intel16_qwen35b_thinking.json`, `intel16_qwen35b_thinking_mt4000.json`
- Arms: `arm_a_qwen35b.json`, `arm_b_qwen35b.json`, artifacts `arm_b_artifacts_qwen/` (9 generated programs)
- Harness deltas: `intel16_single.py` (env-lane wrapper + documented mt override), `arm_a_agentic.py`, `arm_b_singleshot.py` — canonical prompts/grading untouched where marked
