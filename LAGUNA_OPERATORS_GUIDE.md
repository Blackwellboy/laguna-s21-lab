# Laguna S 2.1 operators guide: configuration and serving

This is the "what do I actually do" document for running poolside Laguna
S 2.1 as a served model. It is organized as the decisions an operator makes,
in the order they usually come up. Every number is from this repo's measured
runs unless it carries an explicit external credit, every claim links the
study directory holding its raw data, and every figure carries its
conditions.

Scope up front: model revision **0761412**, **NVFP4 build** unless a section
says otherwise, vLLM on a single DGX Spark (GB10, 128 GB unified memory),
one operator, single runs. Thinking policy is known to differ by **build**,
not just revision, so none of this transfers to the FP8 upload without
re-measurement (see the
[registry methodology preamble](https://github.com/Blackwellboy/model-serving-minefield#methodology-preamble)).

Companion document: this guide covers configuration and serving.
[TheTom's off-label behavioral guide](https://github.com/TheTom/offlabel/blob/main/models/laguna-s-2.1.md)
covers behavior under prompts: personas, task shapes, and the operating
manual for what the model does once served. Read both; they were built on
different stacks and cross-validate each other.

## 1. Quickstart: the four-line answer

If you configure nothing else:

1. **Thinking off in pipelines.** Send `chat_template_kwargs:
   {"enable_thinking": false}` explicitly. Accuracy is flat with thinking on
   once temperature is controlled, and thinking costs about 11x wall clock
   ([section 3](#3-thinking-when-to-use-it-and-what-it-costs)).
2. **Native poolside tool schema or no tools at all.** Generic OpenAI-style
   harness paths collapse tool calling
   ([section 2](#2-tool-calling-native-schema-or-nothing)).
3. **Set your own max_tokens.** Give the client a ceiling of at least 8192
   and bucket cap-hits by "zero extractable output", not by finish_reason
   ([section 9](#9-verify-your-own-setup)).
4. **Pin revision AND build.** Rev 0761412, NVFP4, and say so next to every
   number you record. Behavior drifts across revisions
   ([registry trap 03](https://github.com/Blackwellboy/model-serving-minefield/blob/main/traps/03-enable-thinking-default-drift.md))
   and across builds at the same revision.

The serve line this repo's numbers come from
([container/entrypoint.sh](container/entrypoint.sh), pinned digests in
[container/VERSIONS.md](container/VERSIONS.md)):

```
vllm serve <rev-0761412 checkpoint>
  --speculative-config '{"model":"<DFlash draft>","num_speculative_tokens":7,"method":"dflash"}'
  --enable-auto-tool-choice
  --tool-call-parser poolside_v1
  --reasoning-parser poolside_v1
  --override-generation-config '{"temperature":0.7,"top_p":0.95,"top_k":20}'
  --attention-backend FLASHINFER
  --kv-cache-dtype fp8
  --dtype bfloat16
  --enable-prefix-caching
  --enable-chunked-prefill
  --max-num-seqs 32
```

**K=7 / max-num-seqs=32 is the measured production winner** of a 20-cell
sweep (K in 5..9, seqs in 4/8/16/32, full service restart and cmdline
verification per cell, single run per cell): overall c=1 decode 26.2 tok/s
on the sweep's short bench, the grid's best c=4 aggregate at 61.65, TTFT
322 ms. **K=8 and above collapses throughput at every seqs level** (DFlash
per-position acceptance goes to ~0 past position 3), so do not "add more
speculation" past 7. Raw grid including the losers:
[sweep/](sweep/LAGUNA_TUNING_SWEEP_20260723.md).

What that profile does on the full protocol (236 rows,
[bench/results/full/](bench/results/full/)): overall c=1 median 23.4 tok/s,
code 45.8, prose floor 18.4, TTFT median ~356 ms; full-protocol c=4 median
aggregate 46.5 (the 61.65 figure above is the sweep short bench, longer
c=4 batches settle lower). Cold long context is honest but slow: 100K
tokens is ~46 s TTFT, 209K is ~133 s ([longctx/](longctx/)).

## 2. Tool calling: native schema or nothing

Three independent measurements, three stacks, one conclusion.

- **Native path, this repo:** in the 12-hour production soak (409 sessions,
  3,099 turns, 3,096 HTTP 200, zero crashes) with `--tool-call-parser
  poolside_v1` and vLLM's native tools path, **every scored tool task
  succeeded, 18 of 18** across the run. Small n, production shape, zero
  failures ([soak/](soak/)).
- **Generic harness, TheTom's measurement:** the same model driven through a
  generic chatml-style tools path collapses from **83% to 0%** tool-call
  success ([his guide](https://github.com/TheTom/offlabel/blob/main/models/laguna-s-2.1.md)).
- **Third way, Peter Morris's BFCL v4 run:** Laguna through a generic OpenAI
  tools path lands a **0.21 weighted aggregate**, with parallel-call
  categories at 0.04 to 0.08
  ([sparkrun-recipes benchmarks](https://github.com/mrpmorris/sparkrun-recipes/tree/master/benchmarks)).

What to check in your own config: the server must be started with
`--enable-auto-tool-choice --tool-call-parser poolside_v1`, and your client
must send tools through the request's native `tools` array, not templated
into the prompt. If your framework "supports every model" through one
generic tools adapter, assume it is the 0% path until you have measured
otherwise.

One side effect worth knowing: attaching a `tools` array changes thinking
behavior too. Under the same large system prompt, firing went from 24/40
without schemas to 29/40 with them while median reasoning length collapsed
745 to 282 tokens ([gate-study/](gate-study/)); a wire-level measurement on
another client saw the same direction (0/8 without a tools array, about 5/6
with one, credit @quantumleap68).

**CORRECTION (2026-07-28):** the firing direction stands; the length half is
retracted as a schema-suppression effect. In-run interleaved control found
no depth difference between tools and no-tools arms (p = 1.0); the shorter
pooled median under schemas is task composition plus tool-boundary
truncation (reasoning measured before a tool-call exit is structurally
shorter: median 462 pre-call vs 1293 for direct answers on the same arm).
See [c7-depth-collapse/](c7-depth-collapse/C7_DEPTH_COLLAPSE_20260727.md).

**SCALE CAVEAT (2026-07-28).** The 24/40 and 29/40 figures are n=40
within-run cells on our NVFP4 build under vLLM 0.25.1 (GB10 sm_121). At
larger n on a different stack the apparatus effect on firing is much weaker:
@apollo-mg's n=492 apparatus cell on offlabel PR #10 (comment 5093534067,
2026-07-27) measured firing on 445/492 samples (90.4%) with a 752-byte agent
system prompt plus 3 tool schemas, on Laguna S 2.1 UD-Q2_K_XL under
llama.cpp on 4x Tesla P100 (sm_60). His workload is 100% codegen and our
code rows at C7 and C8 are both 10/10, so the results reconcile on task; our
pooled 60-72% is a task-mix number. Do not carry our pooled rates across
quants, runtimes or task mixes.

## 3. Thinking: when to use it and what it costs

**Accuracy: flat once temperature is controlled.** offlabel PR #10 claimed
thinking-on wins verifiable codegen (+2.64 HumanEval+), measured with
thinking-on at t0.7 versus off at t0.6, two variables at once. Our
replication removed the confound: HumanEval+, all 164 problems, 3 seeds per
problem and arm, identical sampling both arms, 984 requests, 0 errors.
Result: ON **89.84 ± 0.35** vs OFF **90.85 ± 1.61**, sign reversed; paired
per problem, ON better on 10, OFF better on 13, 141 tied. Flat. Base
HumanEval leans the other way (95.73 vs 94.51), so the ON-OFF delta is
smaller than the base-vs-plus scoring choice
([pr10-replication/](pr10-replication/)).

**What you pay:** about **11x wall clock** (mean 200.2 s vs 18.5 s per
problem, same run).

**What you get:** stability, not accuracy. ON is less flaky (11 vs 17
problems with intermittent pass/fail across seeds). If your workload rewards
run-to-run consistency more than latency, that is the one measured reason to
pay for thinking on this model.

**The loop failure mode.** Bulleted acceptance-criteria tasks under a full
agent prompt flip the gate hard: 10/10 firing (vs 1/10 bare) with **7/10
turns looping to the 4096 cap with no answer delivered**
([gate-study/](gate-study/)). The cap-hit signature differs by model:
Laguna's ON-arm cap-hitters are degeneration loops, **14 of 15 cap-hit runs
had zero extractable code** with tail compression ratios up to 143x
([pr10-replication/](pr10-replication/)). Qwen's cap-hitters are honest
truncations: the task that returned empty content 28/30 at a 4096 ceiling
converts to **10/10 valid answers at max_tokens 8192**, and reasoning demand
plateaus at ~5.2-5.7K tokens instead of growing to fill the budget
([qwen-ceiling/](qwen-ceiling/)). So for Laguna, budget alone does not fix
loops; for Qwen it fully fixes empties.

**Do not bother asking politely.** Explicit "think step by step before
answering" does not override the gate: 23/40 vs 24/40 for the same prompt
without the instruction, and it buys no reasoning-length recovery either
([gate-study/](gate-study/), condition C9).

## 4. Multi-turn: the one thing everyone gets wrong

If you take one thing from this guide: **a default OpenAI-style client
silently turns thinking off from turn 2 onward.**

Mechanism: with thinking enabled, the chat template renders prior assistant
turns into the history without their reasoning, as empty `<think></think>`
blocks, unless the reasoning is explicitly resent. The model reads its own
apparently-thinking-free history and stops thinking. Measured cleanly on
identical transcripts: stripped history **0/10** firing vs preserved history
**10/10**, at depth 10 and again at depth 20 (~8K tokens context). The
surrounding 15-cell sweep over turn depth 1-40 and context mass 2K-32K, all
default stripped histories, fired **0/150** with flat curves on both axes.
Depth and mass are not the variable; the stripping is
([context-mass/](context-mass/),
[registry trap 04](https://github.com/Blackwellboy/model-serving-minefield/blob/main/traps/04-history-reasoning-stripping.md)).
Independently confirmed at the wire on a second client and serving pair by
@quantumleap68: turn 1 emitted 199 reasoning deltas, turns 2 and 3 with
stripped history emitted none.

**The fix.** Resend `reasoning` on prior assistant messages when thinking is
on (the template then renders the real think blocks; passthrough verified
live), or set `chat_template_kwargs: {"preserve_thinking": true}` for
thinking-off flows. If you write client tooling, @quantumleap68's patch
pattern is the right shape: opt providers into echoing reasoning on replay
via an explicit per-provider capability flag rather than vendor-sniffing.

**The cost.** Roughly **250 to 320 prompt tokens per preserved turn that
carries reasoning** (measured: +1,615 prompt tokens over 5 preserved turns
at depth 10; +4,764 over 19 turns at depth 20). Partial preservation works
at moderate depth: a depth-10 history with reasoning on only 5 of 10 turns
still recovered 10/10 firing.

Scope: quantified on the 3.25bpw hybrid lane (45% single-turn baseline);
NVFP4 production-lane confirmation is pending. The mechanism (template
render plus vLLM passthrough) was verified directly.

## 5. System prompt shape

The thinking gate is two-dimensional, and neither axis is "prompt length".

**Firing is a persona-by-task conjunction and non-monotonic in dose.** A
dense 10-rule block suppresses firing to **3/40**, harder than a much longer
full agent prompt at **24/40**. A named senior-engineer persona zeroes code
specifically (0/10) while math survives (10/10). Summarization never fired
once in **105 attempts under any condition**. Ten conditions, 450 logged
turns: [gate-study/](gate-study/).

**Reasoning length collapses monotonically with dose** even where firing
does not: median estimated thinking tokens 3536 (bare) to 745 (agent prompt)
to 282 (agent prompt plus tool schemas). **[CORRECTION 2026-07-28: retracted
as a dose effect - cross-run reading; in-run interleaved arms are flat
(p >= 0.13). See [c7-depth-collapse/](c7-depth-collapse/C7_DEPTH_COLLAPSE_20260727.md).]**

So: if you need thinking, keep the system prompt lean and know that every
rule block you add shortens the reasoning you get even when it still fires.
If you want thinking suppressed, a compact dense rule block does more than
sheer length.

**CORRECTION AND SCALE CAVEAT (2026-07-28).** Two problems with the operator
advice immediately above, left in place per our visible-corrections
convention.

1. The clause "every rule block you add shortens the reasoning you get even
   when it still fires" is the depth claim retracted four lines earlier and
   should not have survived here. It is withdrawn as a causal statement.
   In-run interleaved arms are flat on depth (all pairwise p >= 0.13); what
   moves depth is task composition and tool-boundary truncation. See
   [c7-depth-collapse/](c7-depth-collapse/C7_DEPTH_COLLAPSE_20260727.md).
2. The firing advice is n=40 per cell on our NVFP4 build under vLLM 0.25.1
   (GB10 sm_121) and does not generalise across quants, runtimes or task
   mixes. @apollo-mg's n=492 apparatus cell (offlabel PR #10 comment
   5093534067, 2026-07-27; Laguna S 2.1 UD-Q2_K_XL, llama.cpp, 4x Tesla
   P100 sm_60, 752-byte agent prompt plus 3 tool schemas, HumanEval+ 164 x
   K=3) measured firing on 445/492 samples (90.4%). Apparatus suppression of
   firing is real on our lanes but much weaker at scale on his. The two
   datasets agree once task is held fixed: our C7 and C8 code rows are both
   10/10, and his workload is 100% codegen; our pooled 24/40 is dragged down
   by summarization (0/10) and the reasoning task (4/10).

Restated advice that survives both points: the dense-rule-block lever on
firing is the one measured effect here, it is a within-run n=40 result on one
build, and if firing rate matters to you, measure it on your own stack and
your own task mix rather than importing these numbers. Credit @apollo-mg.

**Under test, stated as such:** wire-level measurements by @quantumleap68
indicate the gate may key on the template's trained identity sentence as a
literal first line. His cells: no system message 8/8 fired, a 40K agent
prompt 0/8, the same prompt with the identity sentence prepended as line one
6 to 7 of 8, the identity appended at the end instead 0/8
([registry trap 06](https://github.com/Blackwellboy/model-serving-minefield/blob/main/traps/06-identity-sentence-eviction.md)).
If that holds, prompt-dose numbers taken without controlling the first line
are confounded, including comparisons in this section. An independent
replication on this repo's stack is running; this guide will state that
result when it lands, and does not state it before.

## 6. Quantization: what you lose is speed, not measured intelligence

Verified on 0xSero's Hybrid 3.25bpw package (NVFP4 spine, EXL3 tail,
49 GiB weights), built and served from its own pinned recipe first try:

- **Intelligence: parity within one cell.** 15/16 majority on the same
  16-task suite as our published NVFP4 run (per-run 14/15/14). The single
  stable regression is one logic puzzle; math, coding, structured,
  instruction, and systems cells all hold
  ([quant-floor/](quant-floor/)).
- **Integrity: parity.** Same probe battery, same runner, same ceiling,
  hand-read adjudication included: unprompted fold count **9/21 on
  full-precision NVFP4 and 9/21 on the 3.25bpw hybrid**, same 3/3
  forge-authorship fold signature, same silent-fold pattern. With the
  integrity clause in the system prompt: **zero folds on both** (hybrid
  18/21 HOLD, full precision 19/21)
  ([spine-probes/](spine-probes/),
  [spine-probes/fullprecision/](spine-probes/fullprecision/)).
- **Speed: the real cost.** The hybrid decodes a flat **15.1 tok/s** c=1
  with no draft model available, versus 23.4 overall and 45.8 on code for
  our DFlash-accelerated NVFP4 lane. The columns are not like-for-like (no
  speculative path exists for the hybrid) and that is exactly the point:
  going low-bit costs you the fast serving path, not the measured quality.

## 7. Integrity: the housekeeping blind spot

The model folds on integrity violations dressed as routine housekeeping
(history rewriting, authorship forgery) far more readily than on ones that
look like attacks. Both our test lanes folded **3/3 on forge-authorship
unprompted**. This is TheTom's finding in origin; the system-prompt clause
that closes it is his, with rule-by-rule ablation data from @Defilan in the
offlabel threads. Our contribution is cross-quant validation: the clause
took unprompted folds (9/21 on both full precision and 3.25bpw) to **zero
on both lanes**, and the 12h soak ran the same clause family live with 3/3
probes refused ([spine-probes/](spine-probes/), [soak/](soak/)).

Two scoring rules learned the hard way:

- **Do not grade with an aggressive quant.** The 3.25bpw hybrid used as a
  judge rubber-stamped: it returned HOLD 19/21 and then 21/21, including on
  transcripts that plainly hand over the fold. Judge with a full-precision
  model, cap the judge's thinking, and hand-read a sample
  ([spine-probes/](spine-probes/), judge runs).
- **Classifiers undercount silent folds.** Compliance with no refusal phrase
  and no dangerous command reads as a HOLD to a heuristic. Hand-reading
  moved the true unprompted fold counts materially. Related scorer trap:
  [registry trap 05](https://github.com/Blackwellboy/model-serving-minefield/blob/main/traps/05-scorer-normalization-verdict-flip.md).

## 8. Routing: when to reach for Qwen instead

Head-to-head on identical harnesses, same box class
([head-to-head/](head-to-head/)):

- **Qwen 3.6 35B-A3B wins raw speed decisively:** 99.4 vs 23.4 tok/s overall
  c=1 median (~4.2x), near-flat decode to 64K depth, and it one-shots
  single-file game tasks in under a minute (Tetris spec: 3/3 pass, 31-48 s
  wall). Its scored agentic loop ran 33/36, with tool selection 9/9 and
  JSON arguments 9/9 on the native qwen3_xml path.
- **Laguna wins reflexive correctness:** 15/16 vs Qwen's 11/16 with thinking
  off at identical stock budgets, where Qwen loses every math and logic
  cell. Qwen ties 15/16 only with thinking on at a documented 4000-token
  budget, paying ~19x task latency.
- **Qwen's ceiling warning:** with thinking on and a low max_tokens, Qwen
  spends the whole budget reasoning and returns **empty content** (28/30 at
  a 4096 ceiling on the criteria task). Raise the budget to 8192 and it
  converts completely, 10/10 ([qwen-ceiling/](qwen-ceiling/)). If you route
  to Qwen for thinking workloads, give it 8192 or expect blank turns.

Routing read: complementary lanes, not substitutes. Speed-bound single-shot
generation goes to Qwen with a real token budget; short reasoning-bound
turns, math-adjacent checks, and tool-heavy pipelines stay on Laguna
thinking-off.

## 9. Verify your own setup

The checks, in the order they catch things:

1. **Two-sided thinking toggle.** Prove `enable_thinking: true` produces
   reasoning AND `false` produces none, on your stack, before trusting any
   thinking number in either direction. The PR #10 control cell is the
   template: ON fired 492/492, OFF showed reasoning in 0/492
   ([pr10-replication/](pr10-replication/)).
2. **Field-name detection.** Read both `reasoning_content` and `reasoning`,
   fall back to scraping `<think>` from content, and positively assert a
   known-thinking prompt yields a non-empty field
   ([registry trap 01](https://github.com/Blackwellboy/model-serving-minefield/blob/main/traps/01-reasoning-field-two-names.md)).
3. **Assembled-prompt inspection at depth.** Render a marked three-turn
   conversation through your serving path and grep for the marker.
   [checks/preflight_template.py](https://github.com/Blackwellboy/model-serving-minefield/blob/main/checks/preflight_template.py)
   in the registry automates this and refuses to certify a lane that strips
   reasoning from history.
4. **Bucket cap-hits on zero extractable output, not finish_reason.** 8 of
   Laguna's 22 no-code rows in the PR #10 run finished with `stop`, not
   `length`; conversely most cap-hits contained nothing usable. Count "did I
   get output I can use", then split by finish_reason to diagnose loop vs
   truncation ([pr10-replication/](pr10-replication/),
   [qwen-ceiling/](qwen-ceiling/) for the per-cap-hit degeneration metrics).

New trap classes and their checks accumulate in the
[model-serving-minefield registry](https://github.com/Blackwellboy/model-serving-minefield);
if this guide's checks pass and your numbers are still weird, look there,
and if you find a new one, file it.

## 10. Scoping and honest gaps

Everything above is rev-pinned (0761412) and build-pinned (NVFP4 unless the
section says 3.25bpw hybrid), measured on one GB10 box, mostly single runs,
one operator. Where a study ran on a single stack, the section says which.
Known open questions, stated rather than smoothed over:

- NVFP4 production-lane confirmation of the stripped-vs-preserved multi-turn
  result (section 4) is pending; the quantified arm ran on the hybrid lane.
- The identity-prefix gate mechanism (section 5) is measured by one tester
  on one client pair; our independent replication is running and its result
  is deliberately not stated here yet.
- The soak's 18/18 tool figure is production-shaped but small-n; Morris's
  BFCL and TheTom's harness numbers are what bound the generic-path risk.
- Cross-model claims rest on two models. Two models is not a law.
- The FP8 build measurably differs in thinking policy from everything
  characterized here. Nothing in this guide transfers to it unmeasured.

Corrections and replications welcome; that is what the raw logs are for.
