# Qwen 3.6 35B-A3B empty-at-ceiling map: does budget ever fix it?

> **Dating note:** the `_20260729` slug in this filename is a campaign-day label written ahead of the clock; the actual run/ship date is 2026-07-27 (see the [lab README dating convention](../README.md)). Filename kept so inbound links keep resolving.


TEMPORARY HANDOFF, NOT CANONICAL. Date 2026-07-27. Lane: spark-node-a :8100
(`nvidia/Qwen3.6-35B-A3B-NVFP4` @ 491c2f1e, vLLM, `qwen3` reasoning parser,
thinking on `message.reasoning`, `chat_template_kwargs.enable_thinking: true`).

## Headline

**Yes, budget fixes it, completely and cheaply.** The cross-model gate study's
criteria task, which returned empty content 28/30 at the 4096 ceiling, converts
to **10/10 non-empty, shape-valid answers at 8192** and stays 10/10 at 12288
and 16384. The reasoning the task provokes plateaus at ~5.5 to 6K tokens median,
it does not inflate to fill larger budgets. And the cap-hit reasoning tails at
4096 are **healthy, non-degenerate prose** (median unique-line ratio 0.86,
median zlib ratio 0.33 on the 8000-char tail, no loops, no repetition).

**For Qwen, empty-at-ceiling is genuine truncation, not failure.** The model is
mid-way through a normal-quality reasoning trace when the budget runs out. This
is the Qwen-scoped answer to the cap-hitter re-run question, and it means the
"failures, not truncations" cap-hit pattern does NOT hold for this model at
this ceiling: these are truncations that a 2× budget fully converts.

## Setup

- Criteria task **byte-identical** to the 2026-07-26 cross-model study (the
  driver imports `CRITERIA_TASK` from the original driver module rather than
  copying the text).
- Bare prompt (C0, no system prompt), Qwen generation_config sampling
  (temp 1.0 / top_p 0.95 / top_k 20), nonce-prefixed, concurrency 4.
- Budget axis: ceilings {4096, 8192, 12288, 16384} × 10 samples.
- Shape axis: 4 new structured task shapes @ 12288 × 10 samples (prompts new
  for this study, in the driver).
- Degeneration check on every cap-hit: unique-line ratio + zlib compression
  ratio over the last 8000 reasoning chars (the compression-ratio approach
  from the PR #10 discussion).

## Budget axis (criteria task, C0)

| ceiling | non-empty | shape-valid | cap-hits | med reasoning tok (est) | med completion tok |
|---|---|---|---|---|---|
| 4096 | 2/10 | 2/10 | 10/10 | 3712 | 4096 |
| 8192 | **10/10** | **10/10** | **0/10** | 5188 | 6832 |
| 12288 | 10/10 | 10/10 | 0/10 | 5734 | 7206 |
| 16384 | 10/10 | 10/10 | 0/10 | 5654 | 7263 |

The task's natural cost is ~7K completion tokens (~5.5K reasoning + ~4.3K chars
of answer). 4096 is simply below it. Note the two 4096 successes: both squeezed
a valid answer under the cap (reasoning ~3.5K, then a compressed answer): the
28/30-empty result replicates as 8/10-empty here.

### Degeneration analysis (all 10 cap-hits at 4096)

Per-sample unique-line ratio 0.80 to 0.97, zlib ratio 0.31 to 0.38. For reference,
looped/repetitive text drives unique-line ratio toward 0 and zlib ratio toward
~0.05 to 0.15. Every cap-hit tail reads as ordinary mid-task reasoning. **It is
not "degeneration all the way up": there is no degeneration at all.**

## Shape axis (@12288)

| shape | non-empty | shape-valid | cap-hits | med reasoning tok |
|---|---|---|---|---|
| numbered-requirements variant | 10/10 | 10/10 | 0/10 | 4201 |
| JSON-schema output | 10/10 | 10/10 | 0/10 | 1565 |
| table construction | 10/10 | 10/10 | 0/10 | 2036 |
| multi-step constrained math | 7/10 | 7/10 | **3/10** | 4068 |

Verdict: the behavior is **not criteria-list-specific and not
structured-generally**: it is reasoning-demand-driven. Shapes that provoke
short reasoning (schema, table) never cap; shapes that provoke long reasoning
(criteria lists, constrained math) cap when demand exceeds ceiling. Constrained
math still caps 3/10 even at 12288, on this model the fix is budget relative
to task demand, not task shape.

## Scope and caveats

- One model (Qwen 3.6 35B-A3B NVFP4), one lane (vLLM, MTP), one criteria task
  plus 4 shape probes, n=10 per cell.
- Reasoning tokens are the len/4 estimate (this lane's usage block exposes no
  reasoning_tokens field), same estimator as the prior studies.
- The Laguna finding this contrasts with (its own empties/suppression) is a
  different mechanism; nothing here transfers to Laguna.
- Latency medians are at concurrency 4 and not comparable across studies.

## Files

- `qwen_ceiling_map_driver.py`, driver (imports the 2026-07-26 driver module
  for byte-identity; deviations documented in its docstring)
- `logs/budget_axis.jsonl`, `logs/shape_axis.jsonl`, raw per-sample rows
- `driver_stdout.log`
