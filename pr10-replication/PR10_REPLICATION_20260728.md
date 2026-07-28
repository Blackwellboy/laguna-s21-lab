# PR #10 replication: `enable_thinking` on HumanEval+: Laguna S 2.1 NVFP4 rev 0761412

> **Dating note:** the `_20260728` slug in this filename is a campaign-day label written ahead of the clock; the actual run/ship date is 2026-07-27 (see the [lab README dating convention](../README.md)). Filename kept so inbound links keep resolving.


**Fourth-stack independent replication requested in [TheTom/offlabel PR #10]. Run 2026-07-27.**

## Verdict, up front

**Apollo's +2.64 does not replicate once temperature is held identical across arms.**
On HumanEval+ (the metric the claim was made on) thinking ON scored **89.84%** vs OFF
**90.85%**: the sign reverses (−1.02), and a paired per-problem test says the true
reading is *flat*: of 164 problems, 10 favor ON, 13 favor OFF, 141 tied. On base
HumanEval the delta is +1.22 for ON, also within noise. There is no regime advantage
for thinking on single-turn verifiable codegen on this stack, and it costs ~11× wall
time (mean 200s vs 18.5s per problem).

**What does replicate:** both of Apollo's secondary claims, strongly.
1. **Flakiness direction:** ON produced 11 flaky problems vs OFF 17 (Apollo: 11 vs 24).
   Not halved here, but ON is measurably more run-to-run stable on the problems it can do.
2. **Cap-hitters are degeneration loops, not truncations:** 15/492 ON runs hit the 12,288
   ceiling; 14 of those returned **zero extractable code** with the entire budget spent
   inside the think block, and tail compression ratios of 2.9 to 143× (a coherent tail
   compresses ~2.5 to 3×; ratios of 44/133/143 are hard loops). More budget would not have
   converted them: ON's p95 completion is 6,763 tokens: the cap population isn't the tail
   of the length distribution, it's a separate failure mode. One OFF run also cap-hit
   (HumanEval/64 s0): a 40k-char *content* loop, ratio 20: the failure mode exists with
   thinking off, at 1/15th the rate.

## Numbers

| arm | HumanEval base pass@1 | HumanEval+ pass@1 | flaky | cap-hit | no-extract | fired | mean wall |
|---|---|---|---|---|---|---|---|
| ON  | **95.73** ± 1.06 (96.34 / 94.51 / 96.34) | 89.84 ± 0.35 (89.63 / 89.63 / 90.24) | 11 | 15/492 (3.0%) | 22/492 (4.5%) | 492/492 | 200.2 s |
| OFF | 94.51 ± 0.61 (93.90 / 95.12 / 94.51) | **90.85** ± 1.61 (92.68 / 89.63 / 90.24) | 17 | 1/492 (0.2%) | 1/492 (0.2%) | 0/492 | 18.5 s |
| Δ ON−OFF | **+1.22** | **−1.02** | | | | | |

pass@1 = mean ± sd over 3 seeds; per-seed values in parentheses. n=164 problems per cell,
164×2×3 = 984 requests, 0 transport errors. Scoring: evalplus 0.3.1 `sanitize` +
`evaluate` (its own test execution; no LLM anywhere in the scoring path). A sample with
no extractable code counts as fail.

Paired per-problem (pass-count over 3 seeds per arm):
- **plus:** ON>OFF on 10 problems, OFF>ON on 13, tied 141 → no significant paired difference.
- **base:** ON>OFF on 11, OFF>ON on 7, tied 146 → same conclusion, opposite lean.

The base-vs-plus sign flip inside one run is itself informative: the ON−OFF delta is
smaller than the base-vs-plus measurement choice. Anyone comparing headline numbers
across stacks that scored different variants of "HumanEval" will manufacture a regime
effect out of harness choice alone.

### Where ON actually loses points on plus

The ON failure tail is dominated by its cap-hit loops: HumanEval/116 (ON 0/3 pass,
OFF 3/3), /113 (1/3 vs 3/3), /76, /134, /145. Degeneration is concentrated on specific
problems, not uniform: /116 and /132 looped in all three ON seeds, /145 in two.
A loop-detection stopping rule (Apollo's proposed harness change) would target exactly
these, on our numbers it could recover at most ~1 pt for ON, i.e. it would bring ON to
parity with OFF on plus, not ahead of it.

### No-extractable-answer census (Apollo: 11/492)

ON: 22/492, 14 cap-hit loops + 8 `finish=stop` responses whose content held no fenced
code block (prose + inline fragments after a large think block). OFF: 1/492 (the content
loop). Apollo's ~2% no-answer rate is the right order of magnitude for ON; OFF is an
order lower.

## Methodology (confound eliminations, named)

Built on the merged `scripts/thinking-probes/thinking_ab.py` patterns; run by driver
`pr10_ab.py` (alongside this file).

1. **Sampling confound (the review's main objection): eliminated.** Both arms ran
   temperature 0.7, top_p 0.95, top_k 20, the model card's recommended sampling, sent
   explicitly on every request. Identical bytes both arms except the one kwarg.
   Sampled (t>0) with **3 seeds per (problem, arm)**, same seed for both arms of a pair;
   pass@1 reported as mean ± sd, enabling the flaky-problem count.
2. **Apparatus held at zero:** no system prompt, user message only, the C0 cell of the
   gate-study grid, which is where an all-coding no-apparatus benchmark sits. Thinking
   fired 492/492 with the kwarg on, consistent with C0 code firing 10/10 there.
3. **Arms:** explicit `chat_template_kwargs: {"enable_thinking": true|false}` only
   (absent = ON on this revision per offlabel #5, so "absent" adds nothing).
4. **Control cell:** OFF is the structural control, reasoning must not appear.
   Measured: **0/492** OFF rows show any reasoning or think-marker. Instrument clean.
5. **Interleaving:** submission order (seed, problem, [ON, OFF]) through a 16-worker
   pool: both arms always co-resident in flight; drift/load shared symmetrically.
6. **Nonce adaptation (deviation from thinking_ab.py, with reason):** no nonce: it
   would mutate the benchmark prompt. HumanEval+ items sent byte-identical. Substitutes:
   per-request vLLM `seed`, and vLLM prefix caching is exact-KV reuse (identical output
   distribution; the llama.cpp `cache_prompt` stale-reply hazard the nonce guards
   against does not exist on this stack). `cache_prompt` not sent.
7. **Ceiling:** max_tokens 12,288 both arms, fixed, **no budget retry** (this is also a
   direct test of Apollo's p95-derived ~12k recommendation, verdict below). One retry
   allowed on transport errors only; none occurred.
8. **Field names:** reads `reasoning_content` *and* `reasoning` (this stack's
   poolside_v1 parser emits the latter; single-field readers undercount).
9. **Prompt:** evalplus's canonical `instruction_prefix` verbatim; no assistant
   prefill (evalplus's `_MAGIC_SPLITTER_` trick is incompatible with a thinking arm).

**On the ~12k ceiling:** adequate on this stack. ON p95 completion = 6,763 tokens
(Apollo saw 10,152); the only runs that touched 12,288 were loops that no finite budget
saves. 12k loses nothing vs 16k here and caps loop cost at ~14 wasted minutes each.

## Scope, stated plainly

Single stack: vLLM 0.25.1, NVFP4 W4A16 + DFlash speculative (K=7), FLASHINFER, fp8 KV,
GB10, revision 0761412 pinned, production serving profile (max_num_seqs=32; run shared
the lane with a concurrent 42-request probe battery for its first ~25 min, load
symmetric across interleaved arms). One benchmark, single-turn, one sampling point
(t0.7), n=3 seeds. This says nothing about long-agentic or integrity regimes: our
prior data on those stands. Quantization arm (3.25bpw hybrid) not run this session.

## For PR #10 specifically

- The **regime table's single-turn-codegen row** should not ship with "+2.6 pts, halves
  flakiness" as a cross-stack property. On a second stack, temperature controlled, the
  accuracy delta is flat-to-reversed. The *stability* half of the row (ON less flaky)
  did replicate and is the defensible part.
- The **§5f methodology findings** (cap-hits with no extractable code are failures,
  ~12k ceiling, loop-detection stopping rule) replicate and deserve to land regardless
  of what happens to the regime table's accuracy row. The qualifier matters: a cap-hit
  that still emitted usable code is not automatically a failure. Our own HumanEval/32
  seed 2 hit the ceiling with extractable code (tail compression 2.88, the lowest in
  our cap population) and went to the scorer like any other sample instead of being
  auto-failed. It then failed the evalplus tests on content grounds, as /32 did in all
  six of our runs on both arms, so the clean cap-hit-that-passed case remains
  apollo-mg's /47, not ours. The bucketing criterion here is zero extractable code
  rather than `finish_reason`.
  (Correction 2026-07-27: this bullet previously said /32 "was scored as a pass". The
  shipped eval results, `evidence/samples_on_s2-sanitized_eval_results.json`, score it
  fail on base and plus. The criterion argument stands; the pass claim was wrong.)
- The temperature confound Tom flagged appears to have been **the whole accuracy story**:
  removing it removed the effect. (Consistent with his own review note that a
  lower-temperature arm losing by 2.64 was "not the shape you would predict.")

## Raw data

`raw_turns.jsonl` (984 rows: full content + reasoning, finish_reason, usage, cap-hit,
extractable, tail-compression-ratio for cap-hits, wall time, seeds), six
`samples_{arm}_s{seed}.jsonl` + `-sanitized` + `.eval_results.json`, driver
`pr10_ab.py`, `analyze.py`, `full_run.log`.
