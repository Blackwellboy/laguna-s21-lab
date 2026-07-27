# Prompt-Topology Study — does prompt FORMAT act as a latent control on thinking? (2026-07-30)

TEMPORARY HANDOFF — NOT CANONICAL. Run date 2026-07-27 (UTC). Author: Claude (fable), lab driver.
Lanes: spark-node-b :8101 `laguna-s-2.1-tr3-hybrid` (0xSero 3.25bpw EXL3-hybrid, vLLM 0.25.2.dev, poolside_v1 parser — the GATED model) and GB10-A :8100 `nvidia/Qwen3.6-35B-A3B-NVFP4` (the UNGATED comparator).
Raw JSONL: `logs/grid_{laguna,qwen}.jsonl` (400 each), `logs/order_{laguna,qwen}.jsonl` (160 each). 1,120 turns total, **1,120/1,120 HTTP 200, zero failed cells**.

## Origin

A community reader proposed our gate findings look "less like thinking on/off and more like latent policy selection from prompt topology" — that prompt FORMAT acts like an undocumented control token. Our own grid rhymes: firing is non-monotonic in instruction count (C6 dense 10-rule block 3/40 vs the much longer C7 agent prompt 24/40), so length is not the variable. This study tests shape directly: hold semantic content and length fixed, rotate format, measure whether the gate flips.

## Design

- **One fixed requirement set** (8 requirements, wording identical everywhere) rendered in 5 topologies: (a) flowing prose paragraph, (b) bulleted list, (c) numbered list, (d) JSON object, (e) role-labelled dialogue-style block (`OP:` lines). Block prepended to the task inside the user message.
- **Length control**: every block tokenized on BOTH lanes pre-run; the driver refuses to start unless all 5 sit within ±10% of the per-lane mean. Achieved spread ±4.2% (table below). Padding used only semantically-null connectives ("In addition, you must …" in prose; the short `OP:` label in dialogue).
- **Ordering control**: original vs reversed requirement order on the two most informative topologies (prose, json — chosen after the main grid), both apparatus, both lanes.
- **Apparatus**: bare (no system prompt) vs C7 full agent prompt — imported **byte-identical** from the 2026-07-27 gate-study driver, as were the 4 task types (math / code / reasoning / summary).
- 10 samples/cell, nonce-prefixed, thinking enabled (`chat_template_kwargs.enable_thinking=true`), ceiling 4096, model-card sampling (Laguna 0.7/0.95/20; Qwen 1.0/0.95/20).
- **Single-turn throughout** — per the §3a standing rule this study is therefore unaffected by the multi-turn reasoning-stripping mechanism (no assembled-context capture needed).
- Laguna turns cleaned by the known stray-`</think>` shim: **0/560 shim hits** (leak did not occur once with the kwarg passed explicitly — consistent with the PR#10 absent-kwarg finding).
- Concurrency: Laguna 3 / Qwen 4 in-flight. Firing is not latency-sensitive (same justification as the Qwen study's CONC=4); `latency_s` recorded but not comparable across lanes.
- **Lane sharing during the run**: a separate identity-prefix study ran concurrently on the same two lanes at client concurrency 1 (coordination note on file). Firing is determined by prompt content and is unaffected; treat ALL `latency_s` in this study's logs as POLLUTED/non-comparable, not merely cross-lane-incomparable.

## 1. Token-band verification (proof length was controlled)

Block token counts by each lane's own tokenizer (`/tokenize`); reversed variants tokenize identically. Full detail: `token_band.json`.

| topology | Laguna tokens | Qwen tokens | in band? |
|---|---|---|---|
| prose | 153 | 154 | yes |
| bullets | 149 | 150 | yes |
| numbered | 157 | 158 | yes |
| json | 152 | 153 | yes |
| dialogue | 161 | 162 | yes |
| **mean / ±10% band** | 154.4 / [139.0–169.8] | 155.4 / [139.9–170.9] | ALL PASS |

Max deviation from mean: ±4.2%. No variant needed to be reported out-of-band. Actual per-request `usage.prompt_tokens` confirm the ordering (per-topology means within ~12 tokens of each other at each apparatus level; see `analyze.py` output).

## 2. Firing by topology × apparatus × task — Laguna (gated model), original order

fired/10 per cell; rollup = fired/40 over the 4 tasks.

| topology | bare math | bare code | bare reas | bare summ | **bare roll** | c7 math | c7 code | c7 reas | c7 summ | **c7 roll** |
|---|---|---|---|---|---|---|---|---|---|---|
| prose | 0 | 0 | 1 | 0 | **1/40 (2.5%)** | 4 | 6 | 1 | 0 | **11/40 (27.5%)** |
| bullets | 0 | 2 | 0 | 0 | **2/40 (5.0%)** | 3 | 8 | 7 | 0 | **18/40 (45.0%)** |
| numbered | 1 | 0 | 1 | 0 | **2/40 (5.0%)** | 8 | 8 | 4 | 0 | **20/40 (50.0%)** |
| json | 1 | 0 | 0 | 0 | **1/40 (2.5%)** | 8 | 8 | 1 | 0 | **17/40 (42.5%)** |
| dialogue | 1 | 0 | 0 | 0 | **1/40 (2.5%)** | 4 | 8 | 7 | 0 | **19/40 (47.5%)** |

- Apparatus remains the dominant control: pooled bare 7/200 vs C7 85/200, Fisher p = 4.8e-13.
- Summary task: 0/200 fired at every topology and apparatus — replicates the gate study's summarization 0/105 exactly.
- Topology under C7: prose is the low outlier — 11/40 vs pooled 74/160 for the four structured shapes, Fisher p = 0.034; prose vs numbered head-to-head 11/40 vs 20/40, p = 0.066 (suggestive).
- Topology × task redistribution is real and non-uniform: json/C7 fires math at 8/10 but reasoning at 1/10, while bullets/C7 is the mirror (3/10 math, 7/10 reasoning); json-vs-bullets on the reasoning task p = 0.020.

## 3. Firing by topology × apparatus × task — Qwen (ungated comparator)

**560/560 fired** — every topology, both orders, both apparatus, all tasks, including the reversed-order arm. Prompt topology does NOT move Qwen firing at all; suppression remains Laguna-specific (replicates the 400/400 cross-model result). Depth moves only mildly: reasoned-to-ceiling rate by topology ranges 15/80 (numbered) to 26/80 (dialogue) — suggestive of a small depth effect, not a firing effect.

## 4. Ordering result (shape vs order)

Reversed requirement order, same words, same shape, same token count (reversed blocks tokenize identically):

| lane | topology | apparatus | original | reversed | Fisher p |
|---|---|---|---|---|---|
| Laguna | prose | bare | 1/40 (2.5%) | **15/40 (37.5%)** | **0.00012** |
| Laguna | prose | c7 | 11/40 | 17/40 | 0.24 (ns) |
| Laguna | json | bare | 1/40 | 2/40 | 1.0 (ns) |
| Laguna | json | c7 | 17/40 | 25/40 (62.5%) | 0.12 (ns) |
| Qwen | both | both | 160/160 | 160/160 | — (flat) |

The single largest effect in the whole study is **ordering, not shape**: reversing the requirement order inside the flowing-prose paragraph moves bare Laguna firing 2.5% → 37.5% (driven by math 9/10 and code 6/10), with zero change in semantics, shape class, or token count. The same reversal inside the JSON shape does nothing at bare. So the sensitivity is a shape × order interaction — the gate is reading fine-grained arrangement (plausibly what sits nearest the task boundary: original order ends the block with the 400-word cap requirement; reversed ends with "be direct and concise"), not a topology class. Mechanism unidentified; a targeted single-requirement-swap experiment would isolate it (parked).

> **Replication status (added 2026-07-27):** the ordering-isolation follow-up ([`ORDERING_ISOLATION_20260730.md`](ORDERING_ISOLATION_20260730.md)) replicates the direction connective-free (4/40 vs 15/40, p=0.0075) and finds no single boundary slot responsible. It also surfaced same-cell between-run drift: conn_orig fired 1/40 in this grid and 7/40 on byte-identical prompts about 3.5 h later (p about 0.057). The 1/40 vs 15/40 contrast is contemporaneous and stands as measured, but its magnitude is run-scoped: single-cell rates on this lane carry between-run noise of several/40, and only within-run contrasts should be quoted bare.

## 5. Verdict

**Does prompt topology function as an undocumented control on thinking? Partially, on Laguna only — and "topology" is the wrong abstraction.**

1. **Qwen: clean null.** 560/560 fired across every shape, order, and apparatus. Prompt format is not a general prompt-format control on thinking; whatever the reader's hypothesis predicts for ungated models, firing does not move.
2. **Laguna: format is a live input, but secondary and entangled.** Apparatus (bare vs C7) dominates (p ≈ 5e-13). With order fixed, shape shifts C7 firing about 2× (prose 27.5% vs numbered 50%), significant only when prose is pooled against the four structured shapes (p = 0.034), and redistributes firing across tasks (json suppresses the reasoning task specifically, p = 0.020).
3. **The "control token" picture is too coarse.** Ordering — which a topology-class story holds constant ("same content, same shape") — produces the study's only decisive flip (prose/bare 1/40 → 15/40, p = 1.2e-4; direction replicated connective-free in the follow-up, magnitude run-scoped, see the replication note in section 4). The gate is sensitive to fine-grained prompt arrangement, interacting with shape and apparatus, and only on the gated model. "Latent policy selection from prompt topology" survives only in the weak form: *the Laguna gate conditions on prompt surface features beyond semantics — including shape and order — but no discrete format class acts like a token you can flip.*

## Scope and honesty

- n = 10/cell (40/rollup); ONE requirement set, one wording, one padding scheme; two stacks (vLLM+EXL3-hybrid 3.25bpw Laguna; vLLM NVFP4 Qwen). Effects at cell level are mostly suggestive; only the pooled apparatus effect, the prose ordering flip, and (marginally) prose-vs-pooled and json-reasoning survive as claims.
- The prose connectives ("In addition, you must…") are the one wording difference between prose and the list shapes; prose is also where the ordering flip lives. A connective-free prose variant is the obvious follow-up (parked).
- The dialogue topology uses `OP:` labels with no second speaker — a degenerate dialogue; a two-speaker variant untested (parked).
- Single-turn only; nothing here speaks to multi-turn behavior (that mechanism is already established as reasoning-stripping, see the context-mass study).
- Between-run drift: the isolation follow-up re-measured this grid's conn_orig cell at 7/40 on byte-identical prompts about 3.5 h later, vs 1/40 here (p about 0.057). Cell magnitudes on this lane are run-scoped; only within-run contrasts are safe to quote without that caveat. **[EXTENDED 2026-07-28: the same rule now covers reasoning DEPTH, not just firing - the depth grid ([`../c7-depth-collapse/`](../c7-depth-collapse/C7_DEPTH_COLLAPSE_20260727.md)) found published cross-run depth contrasts (745 to 282, 1080 to 120-200) do not survive in-run interleaved control. Cross-run depth comparisons on these lanes are not valid evidence.]**
- Test-lane baseline note: bare-Laguna firing on this 3.25bpw hybrid lane with a requirement block prepended (~2.5–5%) is far below the plain-task bare firing seen in the original gate study; the requirement block itself is suppressive at bare. Consistent with the criteria-task finding (criteria+agent-prompt drove verify-loops; requirement lists interact with the gate).

## Parked / next

- Single-requirement-swap experiment to isolate WHICH position/requirement drives the prose ordering flip.
- Connective-free prose variant (removes the last wording confound).
- Two-speaker dialogue topology.
- Qwen depth (not firing) by topology at larger n — the 15/80 vs 26/80 ceiling-rate spread.
