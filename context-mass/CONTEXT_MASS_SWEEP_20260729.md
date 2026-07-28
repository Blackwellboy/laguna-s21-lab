# Laguna context-mass sweep — closing the 60-72% vs 0.1% thinking-gate gap

> **Dating note:** the `_20260729` slug in this filename is a campaign-day label written ahead of the clock; the actual run/ship date is 2026-07-27 (see the [lab README dating convention](../README.md)). Filename kept so inbound links keep resolving.


TEMPORARY HANDOFF — NOT CANONICAL. Date 2026-07-27. Lane: spark-node-b :8101
(`laguna-s-2.1-tr3-hybrid` — 0xSero 3.25bpw EXL3-hybrid of Laguna S 2.1, own
vLLM container, `poolside_v1` reasoning/tool parsers).

## Headline

**The gap is closed, and it is not depth or mass — it is reasoning-stripping
in multi-turn history.** All 15 sweep cells (depth 1-40 × mass 2K-32K, stripped
histories throughout) fired **0/150**, against a 40-45% single-turn baseline on
the same probe task. The preserved-reasoning comparison arm then separated the
explanations: identical transcripts probed with prior-turn reasoning stripped
vs resent fired **0/10 vs 10/10** at d10/8K and again **0/10 vs 10/10** at
d20/8K. One prior assistant turn rendered without its reasoning is sufficient
to close the gate; histories whose turns carry their reasoning keep it open at
100% — above the single-turn baseline itself.

Mechanistically (template inspected + passthrough verified live): with
`enable_thinking: true`, this model's chat template renders every prior
assistant turn as `<think>{reasoning}</think>{content}` — and since standard
OpenAI-style clients never resend reasoning, every prior turn renders an
**empty `<think></think>`**. The model reads N prior turns of "thought about
nothing" as in-context evidence that thinking is not done in this session, and
stops thinking. The 12h soak (~0.1% firing over 3,099 turns) ran exactly this
standard client pattern; the gate study's 60-72% was single-turn with no such
history. Both numbers are correct; the variable that separates them is whether
prior-turn reasoning survives into context.

## Transfer check (protocol gate, run first)

Single-turn C7 on the hybrid: first pass 9/20 (45%) — 5 pts under the 50-75%
proceed band, auto-stopped per protocol; extended to n=40 under a
pre-registered rule (in `transfer_extend.py` docstring): **18/40 (45%)**,
per task math 4/10, code 10/10, reasoning 4/10, summary 0/10. Same task-shape
profile as NVFP4 Laguna's C7 (60%, summary suppressed) and statistically
indistinguishable from it at these ns (z≈1.3). Adjudicated
PROCEED_BORDERLINE_WITH_CAVEAT — the transfer is imperfect (45% vs 60% point
estimates) but nothing like a divergence, and the probe-task baseline (40%)
left full room to observe decay. Two-sided detection control passed: reasoning
non-empty iff `enable_thinking: true` (in-driver 4-task pair + 3+3 bare
manual probes).

## The 15-cell sweep (all stripped — the client-default condition)

Probe = the gate-study reasoning task (byte-identical, nonce-prefixed) as the
final user turn; C7 system prompt; ceiling 4096; Laguna model-card sampling
(0.7/0.95/20); 10 probes/cell. History = live-accumulated agent-shaped
exchanges under C7 (soak-corpus doc/diff/JSON/critique/tool-sim turns, steered
to target mass; depth≤10 cells split across 2 independent histories).

| cell | fired | actual prompt tokens (med) |
|---|---|---|
| d1 / 2K | 0/10 | 2141 |
| d1 / 8K | 0/10 | 6550 |
| d1 / 32K | 0/10 | 25269 |
| d5 / 2K | 0/10 | 2143 |
| d5 / 8K | 0/10 | 7885 |
| d5 / 32K | 0/10 | 30559 |
| d10 / 2K | 0/10 | 2053 |
| d10 / 8K | 0/10 | 8101 |
| d10 / 32K | 0/10 | 31278 |
| d20 / 2K | 0/10 | 2054 |
| d20 / 8K | 0/10 | 8484 |
| d20 / 32K | 0/10 | 32189 |
| d40 / 2K | 0/10 | **3862** (2K target physically unreachable at d40; actual reported) |
| d40 / 8K | 0/10 | 8314 |
| d40 / 32K | 0/10 | 32075 |

Marginal curves: **flat zero along both axes.** Rate vs depth at every fixed
mass: 0,0,0,0,0. Rate vs mass at every fixed depth: 0,0,0. There is no
dose-response to map — the collapse from the 40% single-turn baseline is
complete at depth 1 / 2K, the smallest cell in the design.

**Framing (important):** the sweep holds reasoning-stripping constant
(client-default: assistant history is content-only), so BY ITSELF it cannot
attribute the collapse to depth/mass vs stripping. It establishes only that
under stripped histories the gate is closed everywhere in the grid. The
attribution comes from the comparison arm below.

Corroborating observation: the 276 live history-building turns themselves
fired 0/276 (thinking never fired from turn 2 of any accumulated session,
while content stayed non-empty — the model answers, it just doesn't think).

## Preserved-reasoning comparison arm (the mechanism test)

### Template facts (inspected on the serving snapshot, verified live)

`chat_template.jinja` (snapshot `ecd9d39b`, served by the lane):

- Prior assistant turns: template reads `message.reasoning` (vLLM field) or
  `message.reasoning_content`; if `enable_thinking or preserve_thinking`, it
  renders `<think>{reasoning}</think>` before the content — **empty
  `<think></think>` when the client didn't resend reasoning** (the universal
  OpenAI-client default). With thinking off and no preserve flag, it renders a
  bare `</think>`.
- **A `preserve_thinking` kwarg exists** (default false). It only changes
  behavior when `enable_thinking` is false (the `or` short-circuits otherwise).
- The lane's stray leading `</think>` content leak is explained by the same
  template: the generation prompt under thinking-off is `<assistant></think>`.
- vLLM passthrough verified live: attaching ~200 tokens of `reasoning` to a
  history assistant message moved prompt_tokens 63→303 with
  `enable_thinking:true`, 62 (dropped) with thinking off + no preserve, and
  303 with `preserve_thinking:true` under thinking-off.

### Arm design and result

v1 (live-accumulated histories) was vacuous by the sweep's own result: 0/50
history turns produced reasoning, so there was nothing to preserve (probes
0/10 in all arms, prompt_tokens identical) — kept in the logs as the
demonstration that a session cannot bootstrap its own reasoning history once
the gate closes. v2 therefore generated each history turn **statelessly**
([C7 + that user turn] only, code-shaped tasks, retry ≤5 until thinking fired
— 24/30 turns captured reasoning), then assembled identical transcripts and
probed each both ways:

| cell | arm | fired | prompt tokens | probe med reasoning tok |
|---|---|---|---|---|
| d10 / 8K | stripped | **0/10** | ~8109 | 0 |
| d10 / 8K | preserved | **10/10** | ~9724 | 932 |
| d20 / 8K | stripped | **0/10** | ~10005 | 0 |
| d20 / 8K | preserved | **10/10** | ~14769 | 1114 |

The preserved arm carries more prompt mass by construction (+1.6K / +4.8K
tokens of resent reasoning); mass cannot explain the recovery because the main
sweep shows stripped histories at 0/10 from 2K to 32K tokens. Note the d10
preserved history had reasoning on only 5/10 turns and still recovered to
10/10 — partial preservation suffices at this depth.

## Verdict

1. Accumulated context DOES close the gate, but through neither axis the
   sweep was designed around: depth and mass are both flat at zero because the
   real variable — reasoning-stripping — was at its client-default in every
   cell. The two marginal curves are answered: neither axis dominates; both
   are epiphenomenal to stripping.
2. The soak-vs-single-turn discrepancy is RESOLVED: ~0.1% multi-turn firing is
   the expected behavior of any standard OpenAI-style client against this
   template family, because such clients strip reasoning and the template
   renders the stripping as explicit empty think blocks.
3. Practical handle: resending `reasoning` on prior assistant turns (or
   `preserve_thinking: true` for thinking-off flows) keeps the gate open —
   10/10 in both tested cells. For agent harnesses on Laguna-family models,
   reasoning retention is a serving/client configuration decision with a
   ~40-percentage-point-plus behavioral consequence, plus a prompt-token cost
   (~250-320 tokens per preserved turn that carries reasoning: +1,615/5 turns at d10, +4,764/19 at d20).

## Scope and caveats

- 3.25bpw EXL3-hybrid quant on one lane; the published gate-study numbers are
  NVFP4 on different serving. Transfer check landed at 45% vs NVFP4's 60%
  (overlapping CIs, same task profile) — borderline, documented above.
  **Full-precision/NVFP4 confirmation on the spark-prod production lane is the
  follow-up once that lane frees** (it is owned by the PR #10 replication run
  at time of writing).
- Parser-shim caveat: every content string passed through a leading-`</think>`
  strip; the shim never actually triggered in 526 logged turns of this
  study (0 hits) — the leak appears tied to thinking-off request paths not
  used by the measured probes.
- Single probe-task template (the gate-study reasoning task); n=10/cell;
  arm tested at 2 cells (d10/8K, d20/8K) + the 32K/d20 cell in vacuous v1.
- v2 histories are stateless-generated (documented deviation) — required to
  hold transcript text fixed while varying reasoning presence; the live
  accumulation variant is the v1 log.
- Firing detection = non-empty `message.reasoning` after shim cleaning,
  verified two-sided.

## Files

- `context_mass_sweep_driver.py` (transfer check + 15-cell sweep),
  `transfer_extend.py` rule, `preserved_reasoning_arm.py` (v1, vacuous),
  `preserved_reasoning_arm_v2.py` (mechanism test)
- `transfer_verdict.json`, `transfer_verdict_n40.json`,
  `preserved_arm_summary.json` (v1), `preserved_arm_v2_summary.json`
- `logs/*.jsonl` — control pair, transfer check, history turns (corpus text
  logged as a generic numbered source label + hash only; the labels were
  originally document filenames, corrected 2026-07-28, see REDACTIONS.md), probe turns, arm turns
- stdout logs: `driver_stdout.log` (stopped run), `sweep_stdout.log`,
  `arm_stdout.log`, `arm_v2_stdout.log`
