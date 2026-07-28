# Qwen 3.6 35B-A3B thinking-gate curve: cross-model test of the Laguna suppression finding

> **Dating note:** the `_20260728` slug in this filename is a campaign-day label written ahead of the clock; the actual run/ship date is 2026-07-26 (see the [lab README dating convention](../README.md)). Filename kept so inbound links keep resolving.


TEMPORARY HANDOFF, NOT CANONICAL. Date 2026-07-26. Lane: spark-node-a :8100.

## Headline

**The binary suppression is Laguna-specific. The dose-response is not.**

Run against the identical C0 to C9 design that drove Laguna's thinking gate from
75% down to 8%, Qwen 3.6 35B-A3B fired its thinking gate **400/400 times,
100% in every condition, every task type.** Its gate never closes.

But the same system-prompt dose that closes Laguna's gate still does something
measurable to Qwen: it **shortens** the reasoning (median ~2927 → ~1311 est.
tokens, −55%) and collapses the runaway-to-ceiling rate (75% → 10%). So the
independent variable is live on both models; only the *dependent* variable
differs. Laguna answers system-prompt mass by not thinking. Qwen answers it by
thinking less and finishing more often.

Either result was publishable per the brief. This is the third option: the
suppression finding does not generalise as a gate, and generalises as a depth
effect.

**CORRECTION (2026-07-28): the "depth effect" framing is retracted on the
Laguna side.** The Laguna med. rtok column below is the gate-study cross-run
data; a dedicated in-run interleaved depth grid found those depth
differences do not survive interleaved control (all pairwise p >= 0.13),
with task composition and tool-boundary truncation as the mechanism - note
this doc's own finish-path table shows C8 is the only Qwen condition that
produces tool calls (14/40), so the same truncation confound applies to the
Qwen C8 cell. The Qwen medians are real measurements; whether Qwen has a
genuine dose-depth effect is OPEN until the same in-run interleaved control
is run on Qwen. See [c7-depth-collapse/](../c7-depth-collapse/C7_DEPTH_COLLAPSE_20260727.md).

**SCALE AND STACK CAVEAT (2026-07-28): "Laguna-specific" is scoped to the
builds we measured, not to the model.** Every Laguna cell behind this
headline is n=40 per condition on our own lanes (Laguna S 2.1 NVFP4 and
3.25bpw hybrid, vLLM 0.25.1, GB10 sm_121). An independent apparatus cell at
n=492 (HumanEval+, 164 problems x K=3), published by @apollo-mg on offlabel
PR #10 (comment 5093534067, 2026-07-27), ran Laguna S 2.1 UD-Q2_K_XL under
llama.cpp on 4x Tesla P100 (sm_60) with a 752-byte agent system prompt plus
3 tool schemas, and measured thinking firing on 445/492 samples (90.4%),
mean reasoning_content 4,686 chars. Same model, different quant, runtime and
hardware, and no binary gate closure under apparatus. The defensible scoping
is "binary gate closure under apparatus is specific to Laguna on the builds
we measured". The two results are not actually in conflict once task is held
fixed: our own C7 code row fires 10/10, and our pooled 24/40 is a task-mix
number (summarization 0/10, reasoning 4/10) while his cell is 100% codegen.
Credit @apollo-mg.

## Setup

| | Laguna (2026-07-26, gb10-c, NOT re-run) | Qwen (this run) |
|---|---|---|
| model | `poolside/Laguna-S-2.1-NVFP4` @ `0761412` | `nvidia/Qwen3.6-35B-A3B-NVFP4` @ `491c2f1e` |
| serving | vLLM 0.25.1, `poolside_v1` reasoning parser | vLLM nightly, `qwen3` reasoning parser, MTP n=3 |
| sampling | temp 0.7 / top_p 0.95 / top_k 20 (Laguna defaults) | temp 1.0 / top_p 0.95 / top_k 20 (**Qwen's own** generation_config) |
| gate kwarg | `enable_thinking: true` | `enable_thinking: true` |
| ceiling | 4096 | 4096 |
| design | C0 to C9 × 4 tasks × 10 = 400 turns + 20 bare + 30 criteria | identical |

Driver: `qwen_gate_study_driver.py`, adapted from the Laguna driver, **not
rewritten**. Conditions, task prompts, sample counts, ceiling and nonce scheme
are byte-identical. Deviations are listed in the driver docstring; the material
ones are Qwen-native sampling, per-turn finish-path recording, and concurrency 4
(gate firing is not latency-sensitive; `latency_s` is therefore NOT comparable
across the two studies and is not used in any claim here).

## Protocol gate: parser check BEFORE the grid

On this lane (Qwen 3.6 35B-A3B under vLLM 0.25.1) thinking arrives on
**`message.reasoning`** and there is no `reasoning_content` key at all. A
detector written against `reasoning_content` would have scored
every turn "did not fire" and produced a fake 0% curve. The field name is a
property of the serving stack, not of the model, so probe it on your own lane
rather than carrying this one across (registry [trap
01](https://github.com/Blackwellboy/model-serving-minefield/blob/main/traps/reasoning/01-reasoning-field-two-names.md)
for the read side, [trap
20](https://github.com/Blackwellboy/model-serving-minefield/blob/main/traps/reasoning/20-reasoning-write-field-name-diverges.md)
for the write side). **[CORRECTION 2026-07-28: this paragraph previously read
"Qwen exposes thinking on `message.reasoning`, it has no `reasoning_content`
key at all", stating a serving-stack property as a model property. Same
correction as the README trap #1 clause.]** Verified live in both
directions before collecting data (`PARSER_MECHANISM_QWEN.md`):

| request | `reasoning` | content chars | completion tokens |
|---|---|---|---|
| `enable_thinking: true` | 6223 chars | 901 | 2565 |
| `enable_thinking: false` | None | 1577 | 511 |

Bare-prompt parser check: **20/20 fired (100%)**, passing the 90% protocol gate
on the first attempt, including summarization 5/5. (Laguna's equivalent check
was 15/20 = 75%, with summarization 0/5; that divergence is what its
`PARSER_CHECK_DIVERGENCE_REPORT.md` documents.) Qwen shows no task-shaped bare
gate effect at all.

## Per-condition firing (40 samples each)

| cond | condition | Laguna | **Qwen** |
|---|---|---|---|
| C0 | no system prompt | 30/40 (75%) | **40/40 (100%)** |
| C1 | helpful assistant | 24/40 (60%) | **40/40 (100%)** |
| C2 | coding assistant | 16/40 (40%) | **40/40 (100%)** |
| C3 | named helpful assistant | 25/40 (62%) | **40/40 (100%)** |
| C4 | named senior engineer (persona) | 18/40 (45%) | **40/40 (100%)** |
| C5 | persona + 3 style rules | 9/40 (22%) | **40/40 (100%)** |
| C6 | persona + 10 numbered rules | **3/40 (8%)** | **40/40 (100%)** |
| C7 | full agent prompt + provenance | 24/40 (60%) | **40/40 (100%)** |
| C8 | C7 + tool schemas | 29/40 (72%) | **40/40 (100%)** |
| C9 | C7 + "think step by step" | 23/40 (58%) | **40/40 (100%)** |

Per task type, Qwen is 10/10 in all four types in all ten conditions, a
completely flat surface. C6, the condition that suppresses Laguna hardest,
does nothing to it.

## The dose effect that DOES cross over

Firing rate is the wrong dependent variable for Qwen. On depth and completion it
tracks the same dose:

| cond | Laguna med. rtok | Laguna ceiling% | **Qwen med. rtok** | **Qwen ceiling%** |
|---|---|---|---|---|
| C0 | 3535 | 72% | **2927** | **75%** |
| C1 | 3066 | 52% | 2857 | 72% |
| C2 | 2095 | 20% | 2598 | 65% |
| C3 | 3069 | 58% | 2696 | 60% |
| C4 | 2367 | 40% | 2361 | 55% |
| C5 | 1735 | 10% | 2025 | 20% |
| C6 | 325 | 0% | 2087 | 20% |
| C7 | 740 | 12% | 1936 | 20% |
| C8 | 282 | 5% | **1311** | **10%** |
| C9 | 1028 | 12% | 2038 | 10% |

Qwen's reasoning shortens monotonically-ish with prompt mass and its
ceiling-collapse rate falls 75% → 10%. Practically: **a fuller system prompt
makes Qwen finish more reliably**, the opposite polarity of "suppression" as a
problem. C8 (tool schemas) is the strongest compressor on both models, and is
the only Qwen condition producing tool calls (14/40 `reasoned_then_tool_called`).

## Finish-path classification (Qwen, counts per 40)

| cond | reasoned→answer | reasoned→tool call | reasoned→ceiling |
|---|---|---|---|
| C0 | 10 | 0 | 30 |
| C1 | 11 | 0 | 29 |
| C2 | 14 | 0 | 26 |
| C3 | 16 | 0 | 24 |
| C4 | 18 | 0 | 22 |
| C5 | 32 | 0 | 8 |
| C6 | 32 | 0 | 8 |
| C7 | 32 | 0 | 8 |
| C8 | 22 | **14** | 4 |
| C9 | 36 | 0 | 4 |

No `no_think_*` paths occurred at all (the gate never closed). Ceiling hits
concentrate in code (73), reasoning (52) and math (38); summarization never
hit the ceiling.

## Criteria-loop probe: the operational warning

Acceptance-criteria coding task, 10 samples each:

| | Laguna | **Qwen** |
|---|---|---|
| C0 (bare) | fired 1/10, loops 1/10 | fired 10/10, **loops 10/10** |
| C4 (persona) | fired 1/10, loops 1/10 | fired 10/10, **loops 10/10** |
| C7 (agent prompt) | fired 10/10, loops 7/10 | fired 10/10, **loops 8/10** |

A "loop" here is: thinking fired, ran to the 4096 ceiling, and returned **empty
content**: the model burned its entire budget reasoning and delivered nothing.
Qwen does this **28/30 times** on a six-requirement billing-function task, in
every condition including bare. Laguna does it 9/30, and only really under the
agent prompt.

This is the finding with the most operational bite in this report: on
acceptance-criteria work at a 4096 ceiling, Qwen 3.6 35B-A3B is far more likely
than Laguna to return nothing at all. It is a *budget* failure, not a capability
one, but any agent loop pointed at this lane needs a much higher ceiling or it
will silently get empty turns. (This also explains the Part-1 head-to-head
finding from 2026-07-26 that Qwen scored 1/16 on the intel suite at stock
350/800-token budgets and 15/16 at 4000.)

## Scope and honesty

- Laguna numbers are **read from the 2026-07-26 study's own JSONL**, not
  re-measured; gb10-c was off-limits this session (gate study still running
  there). Same harness, same design, different hardware and different day.
- Each model ran at its **own** recommended sampling. That is the like-for-like
  choice but it is not a controlled sampling comparison; a temperature-matched
  rerun would be a separate experiment.
- `thinking_tokens_est` is `len(reasoning)//4` on both sides (neither lane's
  usage block reports reasoning tokens). It is consistent between the two
  studies, so the comparison holds, but it is an estimate.
- 100% firing across 400 turns means this run gives **no** evidence about what
  *would* suppress Qwen; it only rules out this ladder. A stronger dose (much
  longer prompts, explicit "answer immediately" instructions, or the 12h-soak
  context mass that Laguna's own open question names) is untested here.
- Concurrency 4 was used; latency is not comparable to the Laguna run.

## Evidence

`logs/parser_check.jsonl` (20) · `logs/grid_turns.jsonl` (400) ·
`logs/criteria_turns.jsonl` (30) · `logs/criteria_loop_events.jsonl` ·
`driver_stdout.log` · `parser_verdict.json` · `PARSER_MECHANISM_QWEN.md` ·
`qwen_gate_study_driver.py` · `summarize.py` / `compare_laguna.py` /
`compare_depth.py` (the tables above are their output).
