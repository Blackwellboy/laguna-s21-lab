# Does `enable_thinking` help single-turn codegen? A three-stack synthesis across the quant floor

**Laguna S 2.1, HumanEval+, thinking ON vs OFF, three quantization levels, two runtimes, two hardware classes. Assembled 2026-07-27.**

## Verdict, up front

The originally reported +2.64 point thinking-ON gain on HumanEval+ does not survive
temperature control. On the two stacks where both arms ran at an identical temperature,
the sign reverses: ON loses 1.02 points on NVFP4/vLLM and 2.44 points on Q4_K_M/llama.cpp.
The original +2.64 was measured with the arms at different temperatures (ON t0.7, OFF t0.6),
and its ON arm was inferred rather than directly measured, per its author's own note.

What does replicate, on every stack that looked for it, is the failure texture of the ON arm:

1. Cap-hitting runs are degeneration loops with zero extractable code, not truncations
   of almost-finished answers.
2. The ON arm's no-extractable-answer rate is an order of magnitude above OFF.
3. On the problems it can solve, ON is more run-to-run stable (less per-problem flaky)
   than OFF. This was the original report's secondary claim and it held.
4. Thinking costs roughly an order of magnitude in wall clock (10.8x here, 7.5x on the
   Q4_K_M stack) for no accuracy return in this regime.

The practical reading: on single-turn verifiable codegen, thinking buys stability on
solvable problems and a heavy tail of budget-burning loops, at 8x to 11x the latency,
with accuracy flat to negative. This holds from 4-bit class quantization down to the
levels tested, on both vLLM and llama.cpp, on datacenter-class and legacy hardware.

## The three stacks

| stack | who | quant | runtime | hardware | temps | seeds | ON plus | OFF plus | delta ON-OFF |
|---|---|---|---|---|---|---|---|---|---|
| A | Blackwellboy (this repo) | NVFP4 W4A16 | vLLM 0.25.1 | GB10 | 0.7 both arms | 3 | **89.84** | **90.85** | **-1.02** |
| B | TheTom (offlabel maintainer) | Q4_K_M GGUF | poolside llama.cpp fork `04b2b72cb` | GB10 | 0.6 both arms | 1 | 88.4 | 90.9 | about -2.4 |
| C | apollo-mg (original report) | Q2_K_XL GGUF | llama.cpp | P100 | 0.7 ON vs 0.6 OFF | 3 | 90.85 | 88.21 | +2.64 |

Row A is ours: 164 problems x 2 arms x 3 seeds = 984 requests, zero transport errors,
identical request bytes both arms except the one `enable_thinking` kwarg, thinking fired
492/492 ON and appeared 0/492 OFF. Full methodology, confound eliminations, and raw
per-sample data live in [`../pr10-replication/`](../pr10-replication/PR10_REPLICATION_20260728.md);
this document does not restate them.

Row B is TheTom's numbers as posted on offlabel PR #10, paraphrased here with attribution:
single-seed (his own caveat: read his -2.44 as agreeing in sign with our -1.02, not as a
precise magnitude), official evalplus scoring, 12,288 ceiling, 4 of 164 ON runs cap-hit
and all 4 returned zero extractable code, ON cost 8.9x output tokens and 7.5x wall clock.

Row C is the original claim as published: K=3 per arm, but the two arms differ in
temperature, and the ON arm predates the harness's `enable_thinking` plumbing, so ON
status is inferred from run metadata rather than recorded (both per the author's own
disclosure on the PR). Row C is listed as the claim under test, not as a controlled
measurement.

Coincidence warning: apollo-mg's ON figure (90.85) and our OFF figure (90.85) are the
same number. They are unrelated measurements on different stacks.

## What the accuracy deltas actually say

- Two independent temperature-controlled replications, on different runtimes and
  different quant levels, both flip the sign. Our paired per-problem test says the true
  reading on stack A is flat: 10 problems favor ON, 13 favor OFF, 141 tied out of 164.
- The between-stack spread (-1.02 vs -2.44 vs +2.64) is dominated by methodology
  (temperature control, seed count, ON-arm provenance), not by quantization level.
  Nothing in the three-stack picture supports a quant-dependent thinking advantage.
- On our stack the ON-OFF delta is smaller than the base-vs-plus harness choice
  (ON wins base by +1.22 while losing plus by -1.02 in the same run). Cross-stack
  comparisons that mix HumanEval variants will manufacture regime effects out of
  harness choice alone.

## The failure texture, which does replicate

- **Cap-hits with no extractable code.** Ours: 15/492 ON runs hit the 12,288 ceiling,
  14 of them with zero extractable code and the whole budget spent inside the think
  block. TheTom: 4/164, all four zero-extract, with unique-line ratios showing the same
  degeneration signature. The loops concentrate on specific problems rather than
  spreading uniformly: HumanEval/116 and HumanEval/132 (two separate problems) each
  looped in all three of our ON seeds.
- **No-extractable-answer census.** Ours: ON 22/492 vs OFF 1/492. apollo-mg's original
  ~2 percent no-answer rate for ON is the right order of magnitude; OFF sits an order
  lower. The failure mode is not thinking-exclusive (our one OFF cap-hit was a 40k-char
  content loop) but ON multiplies its rate by roughly 15x.
- **Stability on solvable problems. Read the direction carefully: thinking ON is the
  LESS flaky arm.** Ours: 11 ON-flaky problems vs 17 OFF-flaky (a problem is flaky when
  it passes 1 or 2 of 3 seeds). apollo-mg originally saw 11 vs 24, same direction.
  His "halved" magnitude did not replicate; the direction did. This is the defensible
  survivor of the original report. Do not conflate this with the failure-rate axis:
  ON has the higher no-extractable-answer rate (22 vs 1) and the higher loop rate,
  while being more stable per problem on the problems it can solve. "ON is flakier"
  is an inversion of the finding.
- **Wall clock.** Ours: mean 200.2s ON vs 18.5s OFF per problem, a 10.8x ratio.
  TheTom: 7.5x. Same order on both runtimes.

## Corrections on record (do not cite the superseded forms)

1. The original +2.64 headline should not be cited as a measured cross-stack property.
   Its ON arm was inferred and its temperature differed between arms; cite the
   temperature-controlled replications instead.
2. "Cap-hits are failures" in bare form was retracted by its own author. The correct,
   replicated criterion is: cap-hits with no extractable code are failures. A cap-hit
   that still emits usable code goes to the scorer like any other sample.
3. HumanEval/32 was never scored as a pass in our run. The shipped eval results score
   /32 fail on base and plus in all six runs on both arms. The clean example of a
   cap-hit that passed remains apollo-mg's /47, not anything of ours.
4. HumanEval/116 and HumanEval/132 are two separate problems that each looped in all
   three ON seeds. Any reading of "116/132" as a single fraction or a single problem
   is a misparse.

## Open gap, stated honestly

apollo-mg queued a 48k-ceiling rerun of the discriminating cap-hit problems; results
were not posted at assembly time. That rerun bears on the cap-hit tail (whether any
loop eventually terminates given 4x budget) and cannot move the accuracy headline:
on our stack ON p95 completion is 6,763 tokens, so the cap population is not the tail
of the length distribution but a separate failure mode, and our zero-extract cap-hits
show tail compression ratios up to 143x (hard loops that no finite budget converts).
If the 48k rerun surfaces cap-hits that do terminate with passing code, the /47-style
bucket grows and the "no extractable code" criterion does the sorting work, exactly
as designed.

## Scope

Single-turn verifiable codegen (HumanEval/HumanEval+), one model family (Laguna S 2.1),
one sampling point per stack, ceilings near 12k. This says nothing about long-agentic
or integrity regimes; our prior data on those stands elsewhere in this repo. The
quantization coverage is NVFP4 W4A16 and Q4_K_M under temperature control, with the
Q2_K_XL point carrying the uncontrolled original only.

## Provenance

Every number in rows and bullets attributed to us was re-derived this session from the
shipped raw (`../pr10-replication/evidence/raw_turns.jsonl`, 984 rows, plus the six
per-seed eval_results files) rather than copied from earlier prose. External numbers
are attributed to their authors' PR #10 posts and are theirs, not re-derived here.
