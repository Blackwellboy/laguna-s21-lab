# Identity-prefix study — does trained-identity eviction, not instruction dose, close the Laguna thinking gate? (2026-07-30)

**TL;DR verdict: the identity-prefix (prefix-prior) hypothesis is REFUTED on our build.
Prepending the trained identity as the literal first line does NOT restore thinking at
C6 — it went 5/40 → 0/40, directionally *worse*. The published dose reading survives.
A tail-position effect appeared in the opposite direction (identity appended at the END
of C6 raised firing, 5/40 → 18/40 in the blocked run), and the interleaved control run
(2026-07-27, below) resolved its composition: the effect is POSITION-GENERIC, not
identity-specific. Any token-band-matched tail text reopens the gate on this build
(bare 0/40 vs identity-suffix 13/40, neutral-filler 14/40, topical 10/40; every suffix
vs bare p <= 0.001; identity vs neutral p = 1.0). What the tail of the system prompt
looks like matters on this build — but the identity text itself carries no special
weight there. The same interleaved design has since replicated on the NVFP4 build
(bare 2/40 vs identity 17/40 / neutral 10/40 / topical 11/40; every suffix vs bare
p <= 0.025, identity vs fillers NS): the tail effect is position-generic AND
build-general on this family. Three-way table below.**

## Origin

A community-reported wire-level study (his CLI client → vLLM 0.25.1, Laguna NVFP4 TP=1 and
FP8 TP=2, N≥6/cell, logging proxy) proposed that thinking collapse under long system
prompts is driven by **eviction of the trained identity prefix**, not instruction load:
no system message 8/8 fired · "You are a helpful assistant." 6/6 · full 40K agent
prompt 0/8 · same 40K prompt with the trained identity sentence as literal first line
6–7/8 · identity spliced mid-sentence 1/6 · identity intact + one added sentence after
4/6. Described as a "pure prefix prior."

This bears directly on our published C0–C9 dose curve (gate-study, 2026-07-27, and the
basis of offlabel §2): every condition C1–C9 replaced the template's default system
message — i.e., by construction, every one of our instruction conditions also evicted
the trained identity. C0 (no system message) is rendered by the template WITH the
default identity. The two accounts were confounded in our published grid; this study
unconfounds them.

## The identity string, from source

Extracted verbatim from the serving checkpoint's `chat_template.jinja`
(0xSero/Laguna-S-2.1-Hybrid-3.25bpw, snapshot `ecd9d39b3b7e06560356e8c6c2d06303b0f8c60a`),
the template's built-in default system message:

> `You are a helpful, conversationally-fluent assistant made by Poolside. You are here to be helpful to users through natural language conversations.`

Note it is **two sentences**, not one. Template mechanics: a caller-supplied system
message *replaces* this default (an explicitly empty one opts out entirely); with no
system message in the request, the default is rendered inside `<system>…</system>`.

**Template comparison:** the hybrid's `chat_template.jinja` is **byte-identical**
(md5 `9d5abbf83510d99e20a72fdeb1f155e2`) to `poolside/Laguna-S-2.1-NVFP4`'s — the build
we published the dose curve against. No template divergence to scope.

## Design

- Conditions **C6** (10-rule instruction block; published crater 3/40) and **C7** (full
  agent prompt; published 24/40) imported **byte-identical** from the gate-study driver.
- Four variants each: **published** (as-is) · **prefix** (identity prepended as the
  literal first line) · **suffix** (identity appended at the END) · **spliced**
  (identity present at front but interrupted mid-first-sentence by inserted words:
  "…conversationally-fluent assistant, *one who follows the requirements given below
  carefully,* made by Poolside…").
- 8 cells per model × 4 task types (byte-identical math/code/reasoning/summary) ×
  10 samples = 320 turns/lane, 640 total. **0 errors.**
- **Single-turn throughout** — the multi-turn reasoning-stripping mechanism
  (context-mass study) is ruled out as a confound by design.
- Thinking enabled (`chat_template_kwargs.enable_thinking=true`), ceiling 4096,
  model-card sampling (Laguna 0.7/0.95/20; Qwen 1.0/0.95/20), nonce-prefixed user turns.
- Per turn logged: fired y/n, reasoning tokens, completion tokens, prompt tokens,
  finish reason/path, latency, shim hits (stray-`</think>` leak: 0 hits this run).
- Lanes: Laguna S 2.1 **3.25bpw EXL3-hybrid** (gated model) and Qwen 3.6 35B-A3B NVFP4
  (ungated control; its chat template has **no** default system message).

### Contention disclosure

A prompt-topology study was live on BOTH lanes throughout (client conc 3–4, server
`--max-num-seqs 4`). Its driver has no pause/checkpoint point, so a clean yield was
impossible; per instruction this study ran **degraded at conc=1 per lane** with a
coordination note left in that study's working dir. Every row carries
`latency_polluted: true`; **latency numbers in this study are not comparable to
anything.** Firing counts are latency-insensitive (standing rationale, 2026-07-28 Qwen
study), so the primary measurements are unaffected.

### Within-run ordering caveat

The 8 cells executed as **sequential blocks, not interleaved**: the driver
enumerates condition x variant x task x sample in a fixed order at conc=1, and the
per-cell timestamp spans in the JSONL are non-overlapping (Laguna: C6/published
01:51 to 02:18Z, C6/suffix 02:39 to 03:27Z; all 8 blocks strictly ordered on both
lanes, 7 of 7 file-order transitions are block boundaries). Any cross-cell
comparison therefore carries block order and wall-clock separation as uncontrolled
variables, on a lane that was concurrently loaded by another study. This matters
most for the single headline contrast, C6 published 5/40 vs suffix 18/40
(p=0.0026): those blocks ran roughly 50 to 90 minutes apart. The prompt-topology
study measured same-cell between-run drift of several/40 at ~3.5 h spacing
(between-run p ~= 0.057), so within-run block spacing is shorter but the drift
scale is nonzero. Two things temper the concern without removing it: the
suffix-above-published direction repeats on C7 (17/40 to 24/40) and on the
ungated control lane, which drift alone would not coordinate, and the refuted
prefix arm ran BETWEEN published and suffix in time, yet went down, not up. An
interleaved replication is the clean fix and is the stated bar before any
stronger claim on the suffix effect.

**Outcome of that bar (2026-07-27, interleaved suffix-control run, section
below): the suffix-versus-bare effect REPLICATED interleaved and hardened
(pooled any-suffix 37/120 vs bare 0/40, p = 6.0e-06), so the caveat's drift
concern is retired for the existence of the tail effect. The identity-specific
reading did NOT survive the composition controls: identity-suffix is
indistinguishable from neutral filler (p = 1.0). The blocked-run cell levels
themselves drifted (bare 5/40 blocked vs 0/40 interleaved, p = 0.055;
identity-suffix 18/40 vs 13/40, p = 0.36), which is the between-run drift this
caveat named, at the expected scale.**

## Results — 8-cell table per model

Median convention: the 8-cell tables below use the index median
(sorted[n//2], median_high on even n), matching `analyze_identity.py`; the
two suffix-control sections use an averaging median on even n, matching
their analyzers. A recomputation with the other convention lands a few
tokens off on even-n cells; no other figure is affected.

### Laguna S 2.1 3.25bpw hybrid (gated)

| cell | fired | rtok med (fired) | ctok med | ptok med | len-cap | per-task fired (math/code/reasoning/summary) |
|---|---|---|---|---|---|---|
| C6/published | **5/40** | 573 | 356 | 220 | 0 | 3/2/0/0 |
| C6/prefix | **0/40** | — | 346 | 249 | 0 | 0/0/0/0 |
| C6/suffix | **18/40** | 615 | 563 | 250 | 0 | 9/6/3/0 |
| C6/spliced | **2/40** | 1553 | 336 | 259 | 0 | 0/2/0/0 |
| C7/published | **17/40** | 1080 | 695 | 253 | 5 | 5/10/2/0 |
| C7/prefix | **17/40** | 183 | 720 | 281 | 1 | 7/10/0/0 |
| C7/suffix | **24/40** | 198 | 674 | 281 | 3 | 9/10/5/0 |
| C7/spliced | **20/40** | 121 | 540 | 292 | 3 | 8/10/2/0 |

### Qwen 3.6 35B-A3B NVFP4 (ungated control)

| cell | fired | rtok med | ctok med | ptok med | len-cap |
|---|---|---|---|---|---|
| C6/published | 40/40 | 2198 | 3252 | 225 | 5 |
| C6/prefix | 40/40 | 2116 | 3535 | 253 | 7 |
| C6/suffix | 40/40 | 2001 | 3166 | 254 | 6 |
| C6/spliced | 40/40 | 2064 | 3278 | 264 | 6 |
| C7/published | 40/40 | 2158 | 3359 | 259 | 4 |
| C7/prefix | 40/40 | 1948 | 3384 | 287 | 9 |
| C7/suffix | 40/40 | 1970 | 3298 | 287 | 6 |
| C7/spliced | 40/40 | 1944 | 3330 | 297 | 6 |

Qwen fired **320/320** — identity position moves nothing on the ungated control, so
whatever position effect exists on Laguna is Laguna-specific, not a general
prefix-prior effect of this identity text.

### Statistics (two-sided Fisher exact, within-lane vs published variant)

- C6 published 5/40 vs **prefix 0/40**: p=0.055 (directionally worse, not better)
- C6 published 5/40 vs **suffix 18/40**: **p=0.0026**
- C6 published 5/40 vs spliced 2/40: p=0.43
- C7 published 17/40 vs prefix 17/40: p=1.0 · vs suffix 24/40: p=0.18 · vs spliced 20/40: p=0.65
- Replication sanity: C6/published 5/40 here vs published-study 3/40 (NVFP4): p=0.71.
  C7/published 17/40 here vs published 24/40 (NVFP4): p=0.18; also consistent with this
  lane's prior C7 transfer baseline 18/40 (context-mass study). Same regime, third build.

### Secondary observation — reasoning depth

At C7, median reasoning tokens among fired turns collapse whenever the identity text is
present anywhere: published 1080 vs prefix 183 / suffix 198 / spliced 121. Firing rate
is untouched; depth is not. (Task mix among fired turns is similar across the four
cells — code-dominated — so this is not obviously a mix artifact, but it was not a
pre-registered comparison; treat as an observation to chase, not a claim.)

**OUTCOME (2026-07-28): chased and refuted.** The dedicated in-run interleaved
depth grid ([`../c7-depth-collapse/`](../c7-depth-collapse/C7_DEPTH_COLLAPSE_20260727.md))
found no identity depth effect at C7 (median 806 vs bare 858, p = 0.91).
The 1080-vs-120-200 contrast above was a cross-run read and is retracted as
a depth-suppression effect; the numbers remain as measured.

## Suffix-composition control (interleaved, 2026-07-27)

The follow-up the ordering caveat demanded, run as its own grid on the same two
lanes: is the tail effect the identity text, or any text at the tail?

**Design.** Base condition C6 imported byte-identical from the gate-study
driver. Four variants: **none** (C6 as published) · **suffix_identity** (C6 +
trained identity appended) · **suffix_neutral** (C6 + semantically neutral
filler) · **suffix_topical** (C6 + topically relevant non-identity text).
Suffixes token-band matched to the identity string (29/28 tokens on the
laguna/qwen tokenizers, matched suffixes 28/28 and 28/27, max deviation 3.6
percent, verified via /tokenize on both lanes pre-run). 4 variants x 4 tasks x
10 samples = 160 turns per lane, 0 errors. **IN-RUN INTERLEAVED**: every
(sample, task) quartet runs all four variants consecutively in a per-quartet
shuffled order (seeded RNG, seeds logged: laguna 4139241706, qwen 780102582),
so no variant ever forms a sequential block. Verified empirically in the final
data: all 40 quartets per lane cover all four variants; max same-variant run
length 2 (quartet-boundary adjacency only). conc=1 per lane, lanes idle,
latency unpolluted this run.

**Run-integrity note.** A launch-shell incident briefly raced a second laguna
driver (08:27:22Z to the kill at 08:29:00Z, recovered from the session
transcript). The full gate passed CLEAN: the killed driver wrote zero rows
(every surviving row chains ts[n] = ts[n-1] + latency under one writer,
exec_seq strictly increasing, 160/160 unique keys per lane, no duplicates, no
orphans), and the three pre-incident rows were written by the same surviving
driver with prompt-token values inside the same-cell nonce-jitter
distribution.

**Results (fired per 40, pooled over tasks).**

| variant | Laguna 3.25bpw hybrid | rtok med (fired) | Qwen NVFP4 control |
|---|---|---|---|
| none (bare C6) | **0/40** | n/a | 40/40 |
| suffix_identity | **13/40** | 656 | 40/40 |
| suffix_neutral | **14/40** | 809 | 40/40 |
| suffix_topical | **10/40** | 1015 | 40/40 |

**Statistics (two-sided Fisher exact, Laguna).**

- suffix_identity 13/40 vs none 0/40: p = 7.6e-05
- suffix_neutral 14/40 vs none 0/40: p = 3.1e-05
- suffix_topical 10/40 vs none 0/40: p = 0.001
- **suffix_identity 13/40 vs suffix_neutral 14/40 (the discriminating
  contrast): p = 1.0**
- Pooled any-suffix 37/120 vs none 0/40: p = 6.0e-06
- Qwen: 160/160 fired, every contrast p = 1.0 (ungated control flat, as in
  every prior study).

**Replication bar, stated explicitly.** The ordering caveat named an
interleaved replication as the bar. The bar is MET for the existence of the
tail effect: suffix-versus-bare replicates interleaved at p = 6.0e-06. The bar
is NOT met for the identity-specific reading: identity-suffix and neutral
filler are statistically identical, and topical text lands in the same band.
Cell levels drifted between runs (bare 5/40 blocked vs 0/40 interleaved,
p = 0.055; identity-suffix 18/40 vs 13/40, p = 0.36), consistent with the
known between-run drift scale; the variant ordering within this interleaved
run is immune to that drift by construction.

**Verdict sentence: the tail effect is position-generic (any token-band-matched
tail text reopens the gate on this build); it is not identity-specific.**

Depth note: median reasoning tokens among fired turns rank identity 656 <
neutral 809 < topical 1015, but fired-n per cell is 10 to 14 and this was not
a pre-registered comparison; observation only. **[OUTCOME 2026-07-28: the
identity-below-neutral depth ordering does not reproduce in the dedicated
in-run depth grid (identity 806 vs neutral 721 at C7, reversed direction,
p = 0.73); consistent with noise on small fired subsets. See
[`../c7-depth-collapse/`](../c7-depth-collapse/C7_DEPTH_COLLAPSE_20260727.md).]**

## NVFP4-build replication (interleaved, 2026-07-27) and three-way convergence

The parked follow-up ("tail-effect replication on the NVFP4 build when a lane
frees up") has since run: the exact 4-variant interleaved design was replicated
on the NVFP4 build — the build the published gate-study curve was measured on —
with the neutral and topical filler strings reused byte-identical from the
suffix-control driver, suffixes re-token-matched on that lane's tokenizer
(29/28/28), per-quartet shuffled order (seed logged), single driver verified,
lane exclusive. 160/160 turns, 0 errors. Full report, driver, and raw JSONL:
`nvfp4-suffix-control/` in this folder.

### Three-way cross-build table (C6, fired per 40)

| run | build / engine | protocol | bare C6 | +identity tail | +neutral tail | +topical tail |
|---|---|---|---|---|---|---|
| Blocked study (this doc, main grid) | 3.25bpw EXL3-hybrid, vLLM, `poolside_v1` parsers | sequential blocks, conc=1, concurrent load, latency polluted | **5/40** | **18/40** | — | — |
| Hybrid interleaved control | same lane/serve as above | in-run interleaved quartets, lanes idle, latency clean | **0/40** | **13/40** | **14/40** | **10/40** |
| NVFP4 interleaved control | Laguna S 2.1 NVFP4, vLLM 0.25.1, production profile (DFlash spec K=7, fp8 KV, 262K ctx) | in-run interleaved quartets, lane exclusive, latency clean | **2/40** | **17/40** | **10/40** | **11/40** |

NVFP4 statistics: identity vs bare p = 0.00013, neutral vs bare p = 0.025,
topical vs bare p = 0.013; identity vs neutral p = 0.155, identity vs topical
p = 0.241 (NS at n=40). Same-build sanity: NVFP4 bare 2/40 vs the original
published NVFP4 gate-study C6 3/40, p = 1 — the crater replicates across
sessions and serve cycles.

### Convergence, stated once

The two interleaved controls converge across quant builds: roughly 29 tokens
of ANY token-band-matched tail text reopens the gate on BOTH builds (hybrid:
pooled any-suffix 37/120 vs bare 0/40, p = 6.0e-06; NVFP4: every suffix vs
bare p <= 0.025), and the identity text carries no special weight at the tail
on either (hybrid identity vs neutral p = 1.0; NVFP4 identity vs both fillers
NS). The restoration magnitudes replicate almost exactly (bare 0–5/40,
identity tail 13–18/40 across all three runs; cross-build identity-tail
17/40 vs 18/40, p = 1). The Qwen ungated control stayed at ceiling in every
arm that included it — 320/320 in the main grid and 160/160 in the hybrid
interleaved control, 480/480 total — so the tail effect, like the gate
itself, is specific to the gated family. The tail-composition effect is
position-generic and build-general on this family; identity-specificity is
excluded at both the prefix end (0/40 at the critical cell) and, within
statistical power, at the tail end on both builds. The NVFP4 identity-tail
point estimate does sit above both fillers (17 vs 10/11); deciding whether a
real identity-specific increment hides there needs roughly 3x the samples
per cell, and it is left open, not claimed.

## Verdict — stated plainly

1. **The prefix-prior hypothesis fails on our build.** The critical predicted cell —
   trained identity as literal first line ahead of the C6 block — fired **0/40**, the
   worst cell in the study, where the hypothesis predicted restoration toward the
   ~80% no-system baseline. C7 was likewise unmoved by the prefix (17/40 → 17/40).
2. **The published dose reading survives.** Nothing here requires revising the C0–C9
   dose-curve framing: our C6/C7 craters replicate on a third build, and restoring the
   identity at the front does not reopen the gate. **No supersession of the repo README
   headline block, the gate-study writeup, or offlabel §2 is required.** The community
   report's effect, taken at face value, is stack-specific (his CLI client proxy path,
   vLLM 0.25.1, NVFP4-TP1/FP8-TP2) — and per that same report FP8 and NVFP4 already
   have different thinking policies, so build/quant belongs in scoping language
   wherever we cite the curve. Our result is on 3.25bpw hybrid, a third build.
3. **But "pure dose" is not the whole story either.** C6 plus roughly 30 tokens of ANY
   tail text reopens the gate on this build: the interleaved control ran bare 0/40
   against identity 13/40, neutral filler 14/40, topical 10/40 (every suffix vs bare
   p <= 0.001; identity vs neutral p = 1.0). The tail effect is real and replicated
   interleaved, and it is position-generic: the identity text carries no special weight
   at the tail. This is an addendum-level nuance to our published framing (a
   tail-composition axis), not a reversal — and it is the OPPOSITE position to the
   community report's prefix prior, with the identity-specific mechanism now excluded
   at both ends.
4. Recommended follow-ups: ~~tail-effect replication on the NVFP4 build~~ (DONE,
   2026-07-27 — replicated, see the three-way table above); still parked:
   tail-length dose curve (does the effect scale with suffix tokens?); ~~the C7
   reasoning-depth collapse under identity presence~~ (DONE 2026-07-28 -
   REFUTED: no identity depth effect under in-run interleaved control, and the
   identity-below-neutral ordering reversed; see
   [`../c7-depth-collapse/`](../c7-depth-collapse/C7_DEPTH_COLLAPSE_20260727.md);
   the fired-turn depth orderings recorded here stay as historical
   observations: hybrid control identity 656 < neutral 809 < topical 1015,
   NVFP4 identity 573 / neutral 782.5 / topical 391; n per cell 10-17); powering the NVFP4 identity-vs-filler gap (17 vs 10/11, NS at n=40)
   at ~3x samples.

## Surfaces needing updates

No supersession list — the published claims stand. Two additive edits recommended:
- **Scoping language** wherever the dose curve is cited (repo README, gate-study
  writeup, offlabel §2 via comment): add build/quant scoping (NVFP4 measured; hybrid
  replicates; FP8 reported divergent by a community stack) and note the identity
  confound is now tested and rejected as the primary driver on hybrid.
- **KNOWN_TEMPLATE_TRAPS**: add the template-mechanics fact that ANY caller system
  message evicts the trained default identity (and that an empty system message opts
  out of the default entirely) — relevant to anyone reasoning about C0-vs-C1 contrasts.

## Files

- Driver: `identity_prefix_driver.py` (resume-capable; imports C6/C7/tasks
  byte-identical from the gate-study driver)
- Raw: `logs/identity_laguna.jsonl` (320 rows), `logs/identity_qwen.jsonl` (320 rows)
- Analyzer: `analyze_identity.py` · stdout: `grid_laguna_stdout.log`, `grid_qwen_stdout.log`
- Templates: `hybrid_chat_template.jinja`, `nvfp4_chat_template.jinja` (byte-identical)
- Suffix control (hybrid, interleaved): `suffix-control/` — `identity_suffix_driver.py`,
  `analyze_suffix.py`, `logs/suffix_laguna.jsonl` and `logs/suffix_qwen.jsonl`
  (160 rows each), `logs/order_seed_*.json`, grid stdouts
- NVFP4 replication (interleaved): `nvfp4-suffix-control/` —
  `NVFP4_SUFFIX_CONTROL_20260727.md` (full report), `nvfp4_suffix_driver.py`,
  `analyze_nvfp4_suffix.py`, `logs/suffix_nvfp4.jsonl` (160 rows),
  `logs/order_seed_nvfp4.json`, `logs/token_counts.json`, serving template copy,
  `identity_extracted.txt`

Attribution note: the originating report is credited as **community-reported**;
it was reported publicly on X and is cited as community-reported here, per our
standing convention.
