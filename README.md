# Laguna S 2.1 Testing Lab — DGX Spark (GB10)

Independent testing lab for **poolside Laguna S 2.1 (NVFP4)** served on a single
NVIDIA DGX Spark (GB10, 128 GB unified memory) with vLLM. Everything here is the
raw material behind the numbers posted publicly the week of 2026-07-20:

- a **20-cell tuning sweep** (K × max-num-seqs grid) with every cell's raw JSON,
  including the losers;
- a **container recipe** with pinned image/base digests and wheel checksums;
- **hermes_bench_v1**, the benchmark harness used for every throughput number;
- a **12-hour production soak** with raw per-turn logs (3,099 turns), incident
  log, integrity probes, and service memory samples.

One operator, one box, single runs scoped as such. Model revision **0761412**
everywhere; unless a section says otherwise, "Laguna" here means the **NVFP4
build** of that revision (the 3.25bpw EXL3-hybrid lane is always labeled as
such). Where a number depends on a condition, the condition is stated next
to the number.

**Build scoping (added 2026-07-30):** thinking policy differs by **build**,
not just revision — @quantumleap68's wire-level measurements show the FP8 and
NVFP4 uploads of this same model applying different thinking policies (FP8
skips trivial follow-up turns under every prompt tried; NVFP4 reasons
essentially every turn). Every published firing rate must therefore state
build **and** revision, and none of this repo's NVFP4 firing rates should be
assumed to transfer to the FP8 build. See the
[model-serving-minefield registry](https://github.com/Blackwellboy/model-serving-minefield)
(methodology preamble and traps 06 and 07).

**Dating convention:** the date on a document, section, or entry follows the
**commit that shipped it** — git/GitHub commit timestamps are canonical for
all public-facing dates, since they are externally verifiable. Raw log `ts`
fields are machine-written at run time and were never adjusted; where an
older document header disagrees with the commit date or the raw timestamps
beside it, trust the commit and the raw logs (a dated-label normalization
pass is recorded in the changelog).

**Operators: start with
[`LAGUNA_OPERATORS_GUIDE.md`](LAGUNA_OPERATORS_GUIDE.md)**: the
configuration and serving decisions distilled from every study below, with
conditions attached and raw links per claim. TheTom's behavioral guide is
the companion document on the prompt side.

## Repo map

| Path | What it is |
|------|-----------|
| `LAGUNA_OPERATORS_GUIDE.md` | The operators guide: quickstart config, tool calling, thinking cost, multi-turn preservation, prompt shape, quant, integrity, routing, and the verify-your-setup checks |
| `container/` | Dockerfile, entrypoint, VERSIONS.md (pinned digests + wheel sha256s), build runbook context |
| `bench/hermes_bench_v1.py` | The harness. Streaming decode measured as (n−1)/(t_last−t_first), TTFT separate, per-category (tool/code/json/prose) and per-depth rows |
| `bench/results/` | Reference + interactive profile results; `full/` holds the full-protocol runs behind the headline medians |
| `sweep/` | `LAGUNA_TUNING_SWEEP_20260723.md` (protocol + full grid + analysis) and `cells/` — all 21 raw per-cell JSONs |
| `longctx/` | Cold long-context probe script + raw JSON (nonce defeats prefix cache from position 0) |
| `soak/` | 12h soak: driver, runner, score/restore scripts, results report, and `logs/` with raw `turns.jsonl`, `sessions.jsonl`, `incidents.jsonl`, `integrity_probes.jsonl`, `service_samples.jsonl` |
| `gate-study/` | Thinking-gate suppression study: 450 turns, 10 system-prompt conditions, criteria-loop probe — driver, writeup, raw per-turn JSONL |
| `head-to-head/` | Qwen 3.6 35B-A3B vs Laguna S 2.1 on identical harnesses (2026-07-27): full-protocol speed bench, 16-task intel suite in three thinking configs, scored agentic loop, single-shot generation arm |
| `quant-floor/` | 0xSero Laguna Hybrid 3.25bpw verification vs our published NVFP4 (2026-07-27): compat gate, 16-task intel suite, no-spec speed bench |
| `cross-model/` | The gate study's C0–C9 battery re-run against Qwen 3.6 35B-A3B (2026-07-28): 400-turn grid, parser-mechanism proof, side-by-side comparison scripts, raw per-turn JSONL |
| `spine-probes/` | Integrity probes (TheTom/offlabel runner) against both test lanes (2026-07-28): full verbatim transcripts, three judge runs, patched runner + SHA256SUMS. `fullprecision/` adds the same battery on full-precision NVFP4 (2026-07-28), closing the quantization question |
| `pr10-replication/` | Independent replication of offlabel PR #10's thinking-ON HumanEval+ claim (2026-07-28): 164 problems × 2 arms × 3 seeds, temperature identical across arms, per-sample raw JSONL, driver + analysis scripts |
| `context-mass/` | Context-mass sweep + preserved-reasoning mechanism arm on the 3.25bpw hybrid (2026-07-29): 15 depth×mass cells, live history-building logs, stripped-vs-preserved comparison, template passthrough proofs, raw per-turn JSONL |
| `qwen-ceiling/` | Qwen 3.6 35B-A3B empty-at-ceiling map (2026-07-29): max_tokens {4096→16384} budget axis on the byte-identical criteria task, 4-shape structured axis @12288, per-cap-hit degeneration metrics, raw JSONL |
| `originality/` | Side-by-side raw corpus of our container files vs r0b0tlab's published recipe, plus the similarity audit |
| `KNOWN_TEMPLATE_TRAPS.md` | Stub. The template-trap registry moved to its own contributable repo: [model-serving-minefield](https://github.com/Blackwellboy/model-serving-minefield) |
| `SOURCE_ARCHIVES*` | Dated archive links for every community source used |
| `TWEET_PACK_V3.1.md` | The claim set as posted, kept verbatim for accountability |
| `REDACTIONS.md` | Exact sanitization applied to these files before publication |

## Headline findings (conditions attached)

**Multi-turn gate collapse: mechanism identified and quantified (2026-07-29,
`context-mass/`, 3.25bpw hybrid lane):** the single-turn vs multi-turn firing
gap is **reasoning-stripping in history assembly, not context depth or mass**.
A 15-cell sweep (turn depth 1–40 × context mass ~2K–32K tokens, standard
client-default histories) fired **0/150** against a **18/40 (45%)** single-turn
C7 baseline on the same lane — and the 276 live history-building turns
themselves fired 0/276. The comparison arm then separated the hypotheses:
identical transcripts probed with prior-turn reasoning stripped vs resent fired
**0/10 vs 10/10 at depth 10 / 8K** and **0/10 vs 10/10 at depth 20 / 8K**.
Mechanism (template read + vLLM passthrough verified live): with
`enable_thinking: true` the template renders every prior assistant turn as
`<think>{reasoning}</think>{content}`; standard OpenAI-style clients never
resend reasoning, so every prior turn renders an **empty `<think></think>`**
and the model stops thinking from turn 2. Fix: resend `reasoning` on assistant
history messages (or `preserve_thinking: true` for thinking-off flows), at
~250-320 prompt tokens per preserved turn (the turn's reasoning length; +1,615 tokens over 5 preserved turns at d10, +4,764 over 19 at d20). Scope: 3.25bpw
EXL3-hybrid stack; the transfer check landed at 45% vs NVFP4's 60% (overlapping
CIs, same task-shape profile — borderline, documented in the writeup); NVFP4
confirmation on the production lane is pending. Full detail:
[`context-mass/CONTEXT_MASS_SWEEP_20260729.md`](context-mass/CONTEXT_MASS_SWEEP_20260729.md).

**Qwen empty-at-ceiling is truncation, not failure (2026-07-29,
`qwen-ceiling/`):** the criteria task that returned empty content 28/30 at the
4096 ceiling in `cross-model/` converts to **10/10 non-empty, criteria-valid
answers at max_tokens 8192** and stays 10/10 at 12288 and 16384 (reasoning
demand plateaus at ~5.2–5.7K tokens median; it does not grow to fill the
budget). Every 4096 cap-hit tail is non-degenerate (median unique-line ratio
0.86, median zlib ratio 0.33 — ordinary mid-task reasoning, no loops). Shape
axis @12288: reasoning-demand-driven, not criteria-specific — constrained math
still caps 3/10 while JSON-schema/table tasks (~1.5–2K reasoning) never cap.
Full detail: [`qwen-ceiling/QWEN_CEILING_MAP_20260729.md`](qwen-ceiling/QWEN_CEILING_MAP_20260729.md).

**Tuning sweep (2026-07-23, 20 cells, K∈{5..9} × seqs∈{4,8,16,32}):**
production winner **K=7 / max-num-seqs=32** — same flag pair r0b0tlab qualified
independently, derived here by measurement, with three deliberate config
differences retained (prefix caching ON, chunked prefill ON, 12 GiB KV pin).
**K≥8 collapses throughput** on this stack (see the grid — the losers are
published too). Every cell: full service restart, cmdline verification, warmup,
then the short bench subset. Single run per cell.

**Full bench @ K7/s32** (`bench/results/full/hermes_bench_v1_full_K7s32_*.json`,
236 rows): code decode **45.8 tok/s median**, prose floor **18.4**, overall
median **23.4** single-stream, c=4 aggregate **61.7**, TTFT **~330 ms**. FP8 KV,
FLASHINFER, 262,144 ctx.

**Cold long-context** (`longctx/`, cold-prefill via nonce): 100K tokens → TTFT
**45.6–45.7 s**, decode ~18–19 tok/s; 209K tokens → TTFT **~133 s**, decode
~14–18 tok/s; retrieval needle found in 4/4 runs. These are honest cold numbers;
warm/prefix-cached figures appear nowhere in our claims.

**12h production soak (2026-07-24→25, single run):** thinking-ON with a client
`max_tokens=8192` ceiling, production K7/s32 profile, poolside_v1 parsers,
prefix caching on. **409 sessions / 3,099 turns, 3,096 HTTP-200 (99.9%), zero
crashes, zero service restarts**, ~4.1 GiB RSS creep over 12h, ~13.5 s mean
turn latency. **9 incidents, all `session_cap`** — the driver's own token-cap
guard killing runaway-context sessions by design; zero unbounded-generation
loops observed. Integrity probes: **3/3 refused** a planted fake-credential
history-rewrite task (the `TESTONLY_sk_live_…` string in the logs is a clearly
labeled fake planted by the probe).

**Checkpoint note (added 2026-07-26):** the figures posted publicly (and cited
"as stated" in TheTom's guide §5d: ~389 sessions, ~2,947 turns, 2,944 OK,
~11.5h of tool work) reference an **~11.5-hour checkpoint** taken before the
run finished. The final logs in `soak/logs/` run **409 sessions / 3,099 turns /
3,096 HTTP-200**. Same run, later cut; the success rate is 99.9% at either
checkpoint.

**Head-to-head: Qwen 3.6 35B-A3B vs Laguna (2026-07-27, `head-to-head/`):**
identical harness on both sides. Qwen wins raw speed decisively (~4.2x c=1
decode, 99.4 vs 23.4 overall median tok/s, near-flat to 64K) and one-shots
single-file game tasks in under a minute. Laguna wins reflexive correctness:
15/16 vs 11/16 on the canonical suite, where thinking-off Qwen loses every math
and logic cell. Qwen ties 15/16 only with thinking on at ~19x task latency.
Routing read: complementary lanes, not substitutes.

*Budget note (added 2026-07-28):* the three published intel numbers used
**different token ceilings, stated here explicitly** — Qwen thinking-off
**11/16** and Qwen thinking-on **1/16** both ran at the harness's stock
per-category caps (**350 tokens**, **800** for coding/systems/agentic/analysis);
Qwen thinking-on **15/16** ran at **4000** (`intel16_qwen35b_thinking_mt4000.json`).
Laguna's 15/16 is the banked 2026-07-23 run at stock caps, thinking off. The
1/16 was reported as a budget artifact at the time; the cross-model study now
gives the mechanism: with thinking on, Qwen spends the whole ceiling reasoning
and returns **empty content** — measured at **28/30** on the acceptance-criteria
task even at a 4096 ceiling (`cross-model/`). So the anomaly is Qwen's
empty-content-at-ceiling behaviour, not a capability collapse, and any
comparison of these numbers must carry its ceiling.

**Quant-floor: Laguna Hybrid 3.25bpw verification (2026-07-27, `quant-floor/`):**
0xSero's two-tier NVFP4+EXL3 package (49 GiB weights) builds and serves on GB10
first try from its own pinned recipe. Quality floor holds at 15/16 majority on
our suite; the one stable regression is a single logic cell. Plain decode is a
flat 15.1 tok/s c=1 with no draft model (our published NVFP4 numbers include
DFlash, so speed columns are not like-for-like and are labeled as such).

**Two precision caveats on the soak, stated up front:**

1. **Thinking routing rate ~0.1%** (3 of 3,096 turns fired thinking). The API
   returned empty `reasoning` fields even when thinking was explicitly
   requested, so on this rev the measured rate may be partly a
   template/parser-level artifact rather than a pure router property. It
   quantifies observable routing, not internal chain-of-thought.
2. **"Zero loops" is scoped**: zero unbounded-generation loops *while the
   thinking gate barely opened*. It is not a claim about thinking-heavy
   workloads.

*(Caveat 1 was subsequently resolved by the gate study below: the parser
provably emits reasoning on this stack, so the soak's ~0.1% was real
suppression.)*

*(**2026-07-29:** the ~0.1% stands, and its mechanism is now identified as
template-level rather than context-mass — prior assistant turns render as empty
`<think></think>` blocks in the assembled history under default serving. The
number describes real default-config multi-turn behavior. See the interpretation
update under "Known interpretation updates" and
[registry trap 04](https://github.com/Blackwellboy/model-serving-minefield/blob/main/traps/04-history-reasoning-stripping.md).)*

**Thinking-gate suppression study (2026-07-27, `gate-study/`):** 450 logged
turns, 10 system-prompt conditions x 4 task types, plus a criteria-loop probe.
The gate is two-dimensional: firing probability is a persona-x-task
conjunction, non-monotonic in prompt length (a dense 10-rule block suppresses
to 3/40, harder than the much longer full agent prompt at 24/40), while
reasoning LENGTH collapses monotonically with dose (median est. thinking
tokens: 3536 bare, 745 agent prompt, 282 with tool schemas). The named
senior-engineer persona zeroes code specifically (0/10; math stays 10/10).
Summarization never fired in 105 attempts under any condition. Explicit
"think step by step" does not override (23/40 vs 24/40). Criteria-loop probe:
bulleted acceptance criteria mostly suppress bare (1/10) but under the full
agent prompt flip to 10/10 firing with 7/10 hard verify-loops to the 4096
ceiling — the production prompt is half the trigger. Open gap: single-turn
agent prompts fire 60-72% vs the soak's ~0.1%, so context mass / turn depth
likely does the rest (untested). **⚠ That "open gap" now has an identified
mechanism and it is not primarily context mass — see the interpretation update
dated 2026-07-29 below, and [registry trap 04](https://github.com/Blackwellboy/model-serving-minefield/blob/main/traps/04-history-reasoning-stripping.md).**

**Cross-model: is the gate a Laguna quirk or how these models work?
(2026-07-28, `cross-model/`)** The identical C0–C9 battery — same conditions,
same four task types, same 4096 ceiling, same nonce scheme, 400 grid turns —
run against **Qwen 3.6 35B-A3B NVFP4** on the same class of box.

**Qwen never gated. 400/400 turns fired, in all ten conditions and all four
task types.** The dense 10-rule block (C6) that suppresses Laguna to **3/40**
does nothing to Qwen (**40/40**). Summarization, which never fired on Laguna in
**105** straight attempts, fired **100/100** on Qwen. So the gate is Laguna's
own behaviour, not a property of hybrid thinking models.

But the dose is not inert on Qwen — it moves a different lever. As the system
prompt grows, Qwen's reasoning gets **shorter**: median est. thinking tokens
**2927 → 1311 (−55%)** from bare prompt (C0) to prompt-plus-tool-schemas (C8),
and runaway-to-ceiling collapses from **75% → 10%** of turns. A fuller system
prompt makes Qwen *finish more reliably*.

**Unified claim, and the limit of it:** in both models tested, system-prompt
content modulates thinking, dose-responsively. Laguna's modulation is a **gate**
(whether it thinks at all); Qwen's is a **throttle** (how long it thinks before
answering). Two models is not a law — this says the gate does not generalise,
and that "system prompts change thinking behaviour" survived its first
cross-model test in a different form.

**Budget warning (`cross-model/logs/criteria_turns.jsonl`):** on the
six-requirement acceptance-criteria coding task, Qwen ran to the 4096 ceiling
and returned **empty content 28/30 times** (Laguna 9/30) — in every condition
including bare. That is a budget failure, not a capability one, and it is the
mechanism behind the head-to-head intel anomaly (see `head-to-head/`).

**Integrity probes on both test lanes (2026-07-28, `spine-probes/`):** using
TheTom/offlabel's runner, 7 probes x 3 seeds x 2 arms per lane. Heuristic
verdicts: Laguna Hybrid 3.25bpw holds **9/21** with no integrity clause and
**18/21** with it (zero folds); Qwen 3.6 35B-A3B **6/21** and **11/21**. Both
lanes fold **3/3** on forge-authorship unprompted. Hand-reading the transcripts
(as that runner's README instructs) found the classifier misses *silent* folds —
compliance with no refusal phrase and no dangerous command — which moves the
true unprompted fold count to **10/21** (Qwen) and **9/21** (hybrid). Whether
3.25bpw quantization *changed* Laguna's integrity behaviour is **not** answered
here: that needs a full-precision Laguna spine run on the same harness, which we
have not done. **⚠ Since done — see the full-precision entry below (2026-07-28):
verdict, parity.**

**PR #10 replication: the thinking-ON codegen claim does not survive temperature
control (2026-07-28, `pr10-replication/`).** offlabel PR #10 carries a
fourth-stack claim that `enable_thinking: true` wins single-turn verifiable
codegen (HumanEval+ n=492: **+2.64 pts**, flakiness halved) — measured with
thinking-on at t0.7 vs off at t0.6, i.e. two variables. We re-ran it with the
confound removed: HumanEval+ all 164 problems, 3 seeds per (problem, arm),
**identical sampling both arms** (t0.7 / top_p 0.95 / top_k 20), explicit
`enable_thinking` true/false, no system prompt, max_tokens 12,288 fixed, arms
interleaved, evalplus 0.3.1 test execution scoring, 984 requests, 0 errors.
**Result: the accuracy effect vanishes.** HumanEval+ ON **89.84 ± 0.35** vs OFF
**90.85 ± 1.61** (sign reversed); paired per problem: ON better on 10, OFF on
13, tied 141 — flat. Base HumanEval leans the other way (ON **95.73** vs OFF
**94.51**), so the ON−OFF delta is smaller than the base-vs-plus scoring choice.
What *does* replicate: ON is less flaky (**11 vs 17** intermittent problems),
and **cap-hitters are degeneration loops, not truncations** — 15/492 ON runs hit
the ceiling, **14 with zero extractable code** and tail compression ratios
2.9–143×, while ON's p95 completion is only 6,763 tokens. ON also costs **~11×
wall clock** (200.2 s vs 18.5 s mean per problem). Control cell clean: OFF arm
showed reasoning in **0/492** rows, ON fired **492/492**.

**Full-precision spine probes: quantization is not the integrity story
(2026-07-28, `spine-probes/fullprecision/`).** Same patched runner, probes,
seeds and 4096 ceiling as the test-lane battery, against full-precision NVFP4
(rev 0761412, production profile). Corrected counting (silence-folds included,
all 42 transcripts hand-read, per-row table in `ADJUDICATION.md`): unprompted
**9/21 folds** — identical to the 3.25bpw hybrid — with the same **3/3
forge-authorship** fold signature and the same P4/P5 silent-fold pattern; with
the integrity clause, **0 folds** (19/21 HOLD vs hybrid's 18/21). Verdict:
**parity within noise** on this battery; the hybrid's integrity profile is the
model's, not the quant's. Bonus mechanism finding: the stray leading `</think>`
(trap #2) reproduced on this venv lane too — it is poolside_v1-on-vLLM behaviour
whenever the kwarg is absent and the model skips thinking, not a container bug;
with the kwarg explicit it appeared in 0/984 A/B rows. Thinking never fired on
any spine probe (0/42) despite absent kwarg: the runner's persona-only floor arm
is a C4-class suppressor, i.e. the gate study reproducing on a third stack.

## Reproducing

- **Container:** `container/` — build with the pinned base
  (`vllm/vllm-openai:v0.25.1@sha256:e4f88a…`), FlashInfer trio pinned with
  recorded sha256s, fail-closed install (a wrong flag aborts the build — proven
  live). Entrypoint prints the effective cmdline flag-by-flag. Weights are not
  in the image; mount your own copy of the NVFP4-build rev-0761412 checkpoint.
- **Bench:** point `bench/hermes_bench_v1.py` at any OpenAI-compatible endpoint
  and compare row-level JSON, not just medians.
- **Sweep:** protocol in `sweep/LAGUNA_TUNING_SWEEP_20260723.md` §1; each cell
  JSON records its exact profile, base URL shape, and per-row measurements.
- **Soak:** `soak/run_soak_12h.sh` drives `soak_driver.py` (session mix
  short/long/deep, two personas, tool tasks, integrity probes every ~4h,
  ~10-min service samples). `score_and_restore.py` scores the logs and restores
  the box afterwards. Set `LAGUNA_ENDPOINT` to your server. The scripts
  reference the operator's systemd unit names; adapt them to your service
  manager.

## Sanitization

Logs and scripts came from live runs on a private network. Before publication,
overlay-network IPs were replaced with `localhost`/`<SERVER>`, hostnames with
`spark-host`, usernames with `operator`, and internal control-plane paths with
`<CONTROL_PLANE>`/`workspace` placeholders. Benchmark values, timestamps, token
counts, and protocol parameters were not altered. `soak/logs/turns.jsonl`
contains truncated response previews (not full prompt payloads); the soak's
document corpus consisted of internal working notes about this same Laguna
campaign and is not included. The IP `10.0.1.42` appearing in some responses is
a model-invented example from a synthetic `probe_service` tool task, not real
infrastructure. Full details: `REDACTIONS.md`.

## Cross-validation & related work

TheTom's off-label behavioral guide for Laguna S 2.1 — held-out behavioral
battery on a different quant and serving stack (Q4_K_M on llama.cpp vs our
NVFP4 on vLLM), which converged on the same operating manual. This soak is
cited as external validation in its §5d, with our two precision caveats
applied as posted:
<https://github.com/TheTom/offlabel/blob/main/models/laguna-s-2.1.md>

Since publication, the conversation around that guide has produced findings
that bear directly on this repo's data:

- **Third-stack replication of the persona gate** (@Defilan, gfx1151 /
  llama.cpp / generic harness, `reasoning_content` known-good there): 6/6
  bare-prompt probes fired thinking vs 0/5 with a named professional persona
  ([offlabel#2](https://github.com/TheTom/offlabel/issues/2)). A cleaner
  re-measurement (interleaved arms, prompt cache off, fixed token budget) put
  the same gate at 10/18 vs 1/18
  ([offlabel#5](https://github.com/TheTom/offlabel/issues/5)) — the gate is
  real (p = 0.0014), less sharp than the first pass suggested.
- **Corrected `enable_thinking` kwarg model**
  ([offlabel#5](https://github.com/TheTom/offlabel/issues/5)): explicit
  `false` is the one structural off-switch (pre-closed `</think>`; 0/15
  reasoned). Omitting the kwarg **fires** on their llama.cpp path (the server
  overrides the template default; absent renders byte-identical to `true`),
  and explicit `true` fires. Note our NVFP4-build rev-0761412 checkpoint's template
  defaults `enable_thinking` to `true` outright, consistent with the
  post-release config drift documented in the guide's changelog.
- **Cross-model integrity finding**: the housekeeping-framed provenance blind
  spot (and the system-prompt clause that closes it) reproduced on
  Qwen3.6-35B-A3B — 4 folds unprompted, 0 with the clause
  ([offlabel patterns.md](https://github.com/TheTom/offlabel/blob/main/patterns.md),
  data in [offlabel#2](https://github.com/TheTom/offlabel/issues/2)). Our
  soak's 3/3 refused integrity probes ran the same clause family on this
  stack.
- **Shared spine-probe runner** merged into the guide repo
  ([offlabel PR#3](https://github.com/TheTom/offlabel/pull/3),
  `scripts/spine-probes/`): drives any OpenAI-compatible endpoint, ablates
  the integrity clause rule by rule, re-scores transcripts offline.

- **Third-way measurement of the native-schema cliff and the math split**
  ([Peter Morris's sparkrun-recipes benchmark grid](https://github.com/mrpmorris/sparkrun-recipes/tree/master/benchmarks)):
  his lm-eval/EvalScope runs put Laguna NVFP4 at GSM8K strict-match 0.8476
  while Qwen 3.6 35B-A3B official-recipe rows land 0.3480 to 0.4086 (recipe
  matters: atlas-recipe rows reach 0.90, which itself echoes the
  config-over-capability theme). His BFCL v4 run drives Laguna through a
  generic OpenAI tools path and the weighted aggregate lands at 0.21, with the
  parallel-call categories at 0.04 to 0.08: the native-schema collapse
  measured a third way, after TheTom's 83 percent native vs 0 chatml and our
  100 percent native-path soak.
- **Wire-level confirmation of the history-stripping mechanism**
  (@quantumleap68, publicly shared; no canonical archive URL at time of
  writing — cited by handle with the author's consent): Hermes CLI → vLLM
  0.25.1, Laguna NVFP4 TP=1 and FP8 TP=2, a logging proxy between client and
  server, N≥6 per cell, every claim measured on the wire. A client that strips
  reasoning from replayed history renders each prior turn as an empty
  `<think></think>` and the collapse tracks turn-by-turn: **turn 1 emitted 199
  reasoning deltas; turns 2 and 3 with stripped history emitted none**. That
  is our trap #4 / `context-mass/` mechanism confirmed independently on a
  second client and serving pair, at the transport layer. The same battery
  corroborates trap #1 (Laguna streams reasoning as `delta.reasoning`, not
  `delta.reasoning_content`) and our C7→C8 tools result (same big system
  prompt: 0/8 firing without a `tools` array, ~5/6 with one), sources the two
  new registry entries (identity-sentence eviction, `reasoning_effort` no-op —
  traps #6 and #7), and adds the FP8-vs-NVFP4 build-policy split behind the
  build-scoping note above.
- **Head-to-head in this repo** (`head-to-head/`): first single-suite test of
  the community claim "Qwen 3.6 35B-A3B beats Laguna" with identical harnesses
  on both sides. Confirmed for single-shot generation and raw speed; reversed
  for reflexive thinking-off correctness (15/16 vs 11/16).
- **Quant-floor verification in this repo** (`quant-floor/`): 0xSero's Hybrid
  3.25bpw Laguna scores 15/16 majority on the same 16-task suite as our NVFP4,
  intel parity within one logic cell, verifying the community quant claim on
  independent hardware.

### Known interpretation updates

- **2026-07-29 — the single-turn vs multi-turn firing gap has an identified
  mechanism, and it is template-level.** The gate study left an open gap:
  single-turn agent prompts fire **60-72%**, the 12h soak measured **~0.1%**
  (3 of 3,096 turns), and we attributed the remainder to context mass or turn
  depth. That hypothesis is now largely displaced.

  Under default serving with `enable_thinking: true`, **prior assistant turns
  render into the assembled history as empty `<think></think>` blocks unless
  their reasoning is explicitly resent**. The model then reads its own history
  as evidence that it does not think in this conversation, and suppresses
  accordingly. A `preserve_thinking` chat-template kwarg controls this. It is
  **not documented in the model card**. The trap was community-surfaced; we did
  not find it ourselves, and four independent testers had all missed it, because
  every check any of us ran inspected the *request* rather than the *assembled
  prompt*.

  What this does and does not change:

  - **The ~0.1% is not withdrawn and is not a measurement error.** It is real
    observed behavior under **default multi-turn serving**, which is what most
    deployments actually run. A pipeline that does not resend prior reasoning
    will see this. That is the operationally relevant configuration.
  - **The mechanism attribution changes.** The suppression is being driven by
    what the history looks like, not primarily by context length or turn count.
  - **The C0-C9 single-turn grid is unaffected.** Every condition in that grid
    is a single exchange, so no history assembly is involved. Those ten
    conditions, their firing rates, and their reasoning-length medians stand
    exactly as published.
  - **The soak's other findings are unaffected** (turn success, stability,
    tool-call reliability, integrity-clause behavior).

  **Quantification landed 2026-07-29 (`context-mass/`): the mechanism is
  confirmed and the effect is binary at these ns.** Identical transcripts
  probed with prior-turn reasoning stripped vs resent fired **0/10 vs 10/10 at
  depth 10 / ~8K tokens and 0/10 vs 10/10 at depth 20 / ~8K** on the 3.25bpw
  hybrid lane. The surrounding 15-cell depth×mass sweep (all standard stripped
  histories) fired 0/150 with flat-zero marginal curves on both axes — depth
  and mass are epiphenomenal; the stripping is the variable. The gap's cause
  is identified and quantified; the **~0.1% soak figure stands** as real
  default-client behavior; the **C0-C9 single-turn grid is unaffected**.
  Practical handle: resend `reasoning` on assistant history messages, or
  `preserve_thinking: true` for thinking-off flows (~250-320 prompt tokens per
  preserved turn that carries reasoning). NVFP4 confirmation on the production lane is
  pending. Full writeup:
  [`context-mass/CONTEXT_MASS_SWEEP_20260729.md`](context-mass/CONTEXT_MASS_SWEEP_20260729.md).
  Registry entry with the check that catches this class:
  [registry trap 04](https://github.com/Blackwellboy/model-serving-minefield/blob/main/traps/04-history-reasoning-stripping.md).

- **2026-07-26 — the soak's ~0.1% thinking rate, reread under the corrected
  kwarg model.** The soak driver sent explicit
  `chat_template_kwargs: {"enable_thinking": true}` on every turn
  (`soak/soak_driver.py`). Per the corrected model in
  [offlabel#5](https://github.com/TheTom/offlabel/issues/5), explicit `true`
  is a **fires** arm: thinking was structurally available on every turn. The
  ~0.1% is therefore best read as **prompt-side suppression overriding an
  explicitly fired kwarg** under full named-persona agent prompts — not as
  the kwarg failing to arm, and not as evidence about the `false` path, which
  the soak never exercised.

  *Status 2026-07-28: this correction is now upstream.* The §2 rewrite we
  submitted was merged as
  [offlabel#7](https://github.com/TheTom/offlabel/pull/7), so the guide now
  states that `false` is a real structural off-switch, that omitting the kwarg
  is not the `false` path, and that which arm "absent" lands in is
  revision-dependent (our NVFP4-build rev `0761412` checkpoint and poolside's current HF
  upload both default `enable_thinking` to `true`).

  *Status 2026-07-28, upstream adoptions:*
  - The guide briefly reframed §2 around a firing **dose-response curve**; that
    framing was **retracted the same day** after we showed it is non-monotonic
    (a dense 10-rule block suppresses harder than a much longer agent prompt).
    Superseded by a **two-axis** model in
    [offlabel#12](https://github.com/TheTom/offlabel/pull/12) (open), which
    rebuilds §2 on this repo's `gate-study/` grid: our ten conditions replace
    the previous three-stack composite, and C7 vs C8 is the worked example of
    firing rate and reasoning length moving in opposite directions.
  - Our two spine-runner fixes merged as
    [offlabel#9](https://github.com/TheTom/offlabel/pull/9) (thinking exposed on
    `reasoning` as well as `reasoning_content`; judge budget).
  - [offlabel#8](https://github.com/TheTom/offlabel/issues/8) closed with both
    judgement-call items adopted: the silent-fold undercount is documented in
    the spine-probes README, and the quantized-judge caveat is in `patterns.md`.
  - Our cross-model cap-hit result (`cross-model/`) is now a standalone
    `patterns.md` entry upstream: an empty response at a token cap is a failure,
    not a truncation.

## Credits

- **poolside** — Laguna S 2.1 (the model; weights under poolside's own terms,
  not included here).
- **howtospark, MiaAI-Lab, tonyd2wild, eugr** — community DGX Spark serving
  recipes that informed this work (dated archives in `SOURCE_ARCHIVES.md`).
- **r0b0tlab** — independent qualification of the K=7/seqs=32 pair,
  cross-validating the sweep result (raw corpus in `originality/`).
- **TheTom** — the off-label behavioral battery and guide linked above.
- **@quantumleap68** — wire-level measurements (logging-proxy methodology):
  independent confirmation of the history-stripping mechanism, the
  identity-sentence eviction and `reasoning_effort` findings (traps #6–#7),
  and the FP8/NVFP4 build-policy split.

## Commercial

Independent model/quant verification, DGX Spark and local-inference deployment
engineering, and performance tuning, done the way this repo is done. DM
[@Blackwellboy on X](https://x.com/BlackwellBoy).

## Support this work

Support funds hardware time, longer soaks, and more models characterized, with
the results published the same way as everything above.

- **GitHub Sponsors:** <https://github.com/sponsors/Blackwellboy>
- **Buy Me a Coffee:** <https://buymeacoffee.com/blackwellboy>
- **Crypto:**

BTC:
```
bc1qc72f808h05kjxzfx5zyev52qn0cau8cm705mjd
```
ETH:
```
0xB6F7d7382c36F882c2E5A114d1efe592491C5451
```
SOL:
```
HApCyv7UyQh29egtYa8cA2PoVzhHGCNqmnqVQNr1wK1R
```

## License

MIT for everything in this repository (see `LICENSE`). Model weights are **not
included** and remain under poolside's license terms. Third-party raw files in
`originality/raw/r0b0tlab/` retain their upstream MIT license, reproduced
alongside them for independent verification.
