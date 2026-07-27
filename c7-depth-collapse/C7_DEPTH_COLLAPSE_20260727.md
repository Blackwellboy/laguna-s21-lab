# C7 depth-collapse follow-up - what controls reasoning DEPTH, as distinct from firing?

**Date:** 2026-07-27 | **Lane:** Laguna S 2.1 NVFP4 (checkpoint 0761412, vLLM 0.25.1, DFlash K=7, production profile) | **Design:** 5 arms × 4 tasks × 10 samples = 200 turns, in-run interleaved, single driver, conc=1, 0 errors.

## TL;DR

**The depth-collapse pattern does not replicate under in-run interleaved control.** Neither the tool-schema depth collapse (prior cross-run: 740→282 median est. reasoning tokens) nor the identity-suffix depth collapse (prior: ~1080→120-200) reproduces when all arms run interleaved in one session: depth among fired is statistically flat across all five arms (all pairwise Mann-Whitney p ≥ 0.13). What *does* structure depth, strongly, is (a) **task type** and (b) in tool arms, **whether the turn exits to a tool call** - turns that end in `tool_calls` carry far shorter pre-call reasoning (median 462 / 136 est. tokens) than turns that answer directly (1293 / 847) or run to ceiling (~3100). The earlier "depth collapse" readings were cross-run comparisons and are best explained by between-run drift plus task-composition weighting plus tool-boundary truncation - not by a depth-suppression dial.

## Question

Two prior observations suggested interventions that raise or hold thinking *firing* while collapsing *depth*: tool schemas at C7→C8 (firing 60→72%, median est. reasoning tokens 740→282, gate study 2026-07-27) and identity-anywhere at C7 (17→17-24/40, ~1080→120-200). The tail-composition controls also showed depth ordering by suffix type (identity 656 < neutral 809 < topical 1015 among fired). Is there a depth control separate from the firing gate?

## Design

Base condition C7 (the gate-study agent prompt, fires ~17-24/40 on this lane - chosen so cells FIRE, since depth is the dependent variable). Five arms, interleaved per-(sample,task) quintet with seeded shuffled order (seed 3699494556):

| arm | system prompt | tools in request |
|---|---|---|
| c7_bare | C7 verbatim | no |
| c7_identity | C7 + trained identity suffix | no |
| c7_neutral | C7 + token-matched neutral filler | no |
| c7_tools | C7 verbatim (== gate-study C8) | yes (3 schemas) |
| c7_identity_tools | C7 + identity suffix | yes |

Apparatus strings byte-identical to the published gate-study driver (C7, TOOLS, TASKS) and prior suffix drivers (NEUTRAL). Identity string extracted this session from the serving checkpoint's chat template (template md5 verified pre-run). Sampling: temp 0.7 / top_p 0.95 / top_k 20, max_tokens 4096, enable_thinking=true. Token bands: identity 29, neutral 28 tokens (3.4% dev).

Pre-stated analysis plan (in driver docstring before run): primary = median est. reasoning tokens among FIRED per arm with n-fired stated; secondary = firing rates; question of record = does identity+tools stack additively or floor.

## Primary result: depth among fired

| arm | n fired | median | IQR | mean | at ceiling |
|---|---|---|---|---|---|
| c7_bare | 20/40 | 858 | [121, 2132] | 1191 | 3 |
| c7_identity | 22/40 | 806 | [136, 1682] | 991 | 2 |
| c7_neutral | 19/40 | 721 | [329, 1011] | 978 | 2 |
| c7_tools | 27/40 | **933** | [127, 1454] | 1081 | 3 |
| c7_identity_tools | 26/40 | 474 | [121, 1062] | 785 | 2 |

Median convention: plain `statistics.median` (averaging; 805.5 and 474.0 appear rounded in the table). The gate study's `summary.json` used `median_high`; the difference is a few tokens and moves no comparison. Scipy cross-check of the key pairs matches the hand-rolled test to two decimals.

All pairwise Mann-Whitney two-sided p ≥ 0.13 (bare vs tools p=1.0; bare vs identity p=0.91; tools vs identity_tools p=0.13). n-fired per arm is 19-27; depth medians on n this size are fragile and the IQRs are enormous - but the *direction* alone already refutes the prior reading: the tools arm has the **highest** median depth in this run, where the cross-run comparison had it collapsed to 282.

**Answer to the question of record (additive vs floor):** neither is established. c7_identity_tools has the lowest median (474) and the ordering is consistent with weak stacking, but tools-vs-both p=0.13 - hypothesis-grade only, not a result.

## Depth is task-structured, not arm-structured

Per-task medians among fired (n_fired):

| arm | math | code | reasoning | summary |
|---|---|---|---|---|
| c7_bare | 121 (8) | 2130 (10) | 1419 (2) | - (0) |
| c7_identity | 123 (9) | 1756 (10) | 864 (3) | - (0) |
| c7_neutral | 142 (4) | 1064 (8) | 675 (7) | - (0) |
| c7_tools | 122 (10) | 1464 (10) | 1257 (7) | - (0) |
| c7_identity_tools | 116 (10) | 1274 (10) | 940 (6) | - (0) |

- **Math is a ~120-token floor in every arm.** **Code is the deep cell (1064-2130).** **Summary never fired, 0/50 attempts per arm** - third independent replication of the gate study's summarization-never-fires result on this build.
- Arm-level medians are therefore **composition-weighted**: which tasks an arm happens to fire on moves its pooled median by hundreds of tokens without any per-task depth change. (e.g. c7_neutral fired on only 4 math but 7 reasoning turns; c7_bare on 8 math but only 2 reasoning.) This same mechanism can manufacture a "collapse" between two runs whose firing composition drifted.
- Within-task (exploratory, not pre-stated): code all-pairs NS (p ≥ 0.17). Reasoning shows neutral < tools (675 vs 1257, p=0.006, n=7 vs 7) - small-n, multiple comparisons, hypothesis-grade only.

## Tool-boundary truncation, not depth suppression

Within the tool arms, depth among fired splits sharply by exit type:

| arm | finish | n | median depth |
|---|---|---|---|
| c7_tools | tool_calls | 20 | 462 |
| c7_tools | stop (direct answer) | 4 | 1293 |
| c7_tools | length | 3 | 3162 |
| c7_identity_tools | tool_calls | 20 | 136 |
| c7_identity_tools | stop | 4 | 847 |
| c7_identity_tools | length | 2 | 3019 |

When the model decides to call a tool, it reasons briefly and exits - the reasoning episode is **truncated at the tool boundary**, not suppressed. 20/40 turns in each tool arm ended in `tool_calls` (0 in the no-tool arms). A run where tool-call turns dominate the fired set will show a collapsed pooled median for purely structural reasons. This is the most parsimonious mechanism for the published C8 median of 282.

## Secondary: firing

bare 20/40, identity 22/40, neutral 19/40, tools 27/40, identity_tools 26/40 - all pairwise Fisher NS (min p=0.11). Directions are consistent with the published effects (tools raise firing: 50%→67.5%; suffixes ~flat at C7), but at n=40 nothing separates. Note bare C7 fired 50% here vs 42.5-60% in prior runs - within the documented between-run drift band. Tools and identity+tools are indistinguishable on firing (27 vs 26) - no stacking on the gate either.

## Integrity

200/200 rows, 0 errors, 0 duplicate cells, 0 `</think>` shim hits. Tool calls: 20 per tool arm, 0 elsewhere. finish_reasons: stop 148 / tool_calls 40 / length 12. Latency median 13.7 s, max 133 s, conc=1, lane exclusive. Kernel-level lane verification (boot log): DFlash num_spec_tokens=7, max_num_seqs=32, KV pin 12 GiB fp8, prefix caching + chunked prefill, batched 8192, reasoning_parser poolside_v1, no sweep-env override present; serving template md5 match. Single driver confirmed pre-run (process-table check); interleaved order seed logged.

## Caveats

1. **n-fired 19-27 per arm; depth IQRs span 20×.** A real 1.5-2× median shift could hide here. This run refutes the *large* collapse readings (5-9×), not any subtle effect.
2. **Cross-run depth comparisons on this lane are not valid evidence** - same-cell firing drifts between runs (documented 2026-07-27), and pooled depth medians additionally inherit composition drift. Depth claims require in-run interleaved arms (this protocol).
3. Est. reasoning tokens = chars/4 where usage doesn't report reasoning tokens - consistent across arms, so comparisons stand, absolute values approximate.
4. The prior tail-composition depth ordering (identity 656 < neutral 809 < topical 1015) was observed at C6 on fired subsets of n=13-17; this run's C7 equivalents (806 / 721) do not reproduce an identity<neutral gap. Consistent with noise on small fired subsets.

## Relation to prior claims

- Gate study C7→C8 "length collapses with dose" (740→282): the firing direction replicates; the **depth collapse should be reinterpreted** as tool-boundary truncation + composition weighting until an in-run replication shows otherwise.
- Identity-anywhere "depth 1080→120-200": does not replicate in-run (806 vs 858, p=0.91); retract as a depth effect.
- Summarization-never-fires: replicated again (0/200 this run).

## Parked follow-ups

- 3× samples on the code cell only (the deep, always-firing cell) for a properly powered within-task depth A/B.
- Multi-turn: depth after tool RESULTS return (the truncation account predicts reasoning resumes; a suppression account predicts it stays shallow).
- identity+tools stacking hint (p=0.13) folds into the code-cell powered rerun.

## Files

- `depth_driver.py` - driver (apparatus imports byte-identical from gate-study driver)
- `analyze_depth.py`, `analysis_stdout.txt` - pre-stated analysis
- `exploratory_within_task.txt`, `toolcall_split.txt` - labeled exploratory cuts
- `logs/depth_c7.jsonl` - 200 raw rows | `logs/order_seed_depth.json` | `logs/token_counts.json`
- `conditions.json` - serving config, template md5, extraction provenance
- `identity_extracted.txt` - identity string as extracted from the serving template this session
