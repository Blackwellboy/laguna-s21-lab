# NVFP4 suffix-control replication (NVFP4 lane, 2026-07-27)

Status: COMPLETE. 160/160 turns, 0 errors, interleave verified in emitted
data. Verdict: POSITION-GENERIC tail effect on the NVFP4 build (all three
matched suffixes lift firing over no-suffix; identity is not significantly
above the matched fillers at n=40).

## Why

The identity-prefix study (hybrid 3.25bpw build) found identity text
at the TAIL of C6 tripled thinking-firing (5/40 to 18/40, p=0.0026), while
identity as a PREFIX went to 0/40, refuting the community prefix-prior claim
on that build. The hybrid-lane interleaved 4-variant suffix control unconfounds
identity-vs-any-30-tokens on the hybrid. This run replicates that exact
4-variant design on the NVFP4 build, the build the published gate-study curve
was measured on. Replication completes the three-build story; divergence is a
quant-scoped finding. Either outcome publishes.

## Serving verification (kernel-level)

- Host: NVFP4 lane, unparked per park-marker recipe
  (the lane's systemd user unit, production profile
  K=7 / max-num-seqs=32), re-parked at session end.
- /proc cmdline of serving pid confirmed model path
  hf/poolside--Laguna-S-2.1-NVFP4-0761412 with matched DFlash draft,
  num_speculative_tokens=7, method=dflash, FLASHINFER, fp8 KV,
  poolside_v1 tool + reasoning parsers, override temp 0.7 / top_p 0.95 /
  top_k 20, max-model-len 262144.
- Engine: vLLM 0.25.1 (system_fingerprint vllm-0.25.1-5f936350).
- Trivial completion probe returned normally (known stray "</think>" prefix
  present, handled by the shim-strip in measurement, counted as shim_hit).

## Template identity check

chat_template.jinja extracted FROM THE SERVING CHECKPOINT:
md5 = 9d5abbf83510d99e20a72fdeb1f155e2. MATCH with the expected value
(byte-identical to the hybrid build's template per the prior study). No
template-divergence scope note needed.

Identity string extracted verbatim from that template (two sentences, ends
"natural language conversations."), stored in identity_extracted.txt; the
driver loads it from that file, never from a transcription.

## Design

Base condition C6 (persona + 10 numbered rules), imported byte-identical from
the 2026-07-27 gate-study driver (same import the identity-prefix and hybrid
suffix drivers use). Four tail variants, token-band controlled to the
identity string on THIS lane's tokenizer via /tokenize pre-run:

- identity 29 tokens, neutral 28 (3.4 pct dev), topical 28 (3.4 pct dev)

Variants: none / suffix_identity / suffix_neutral / suffix_topical.
NEUTRAL and TOPICAL filler strings are byte-identical reuses of the hybrid
suffix-control driver's constants (not re-authored).

4 variants x 4 tasks (math, code, reasoning, summary) x 10 samples =
160 turns, single-turn, max_tokens 4096, temp 0.7 / top_p 0.95 / top_k 20,
enable_thinking=true, same as the gate study's recorded settings.

Protocol: in-run interleaved; every consecutive quartet covers all four
variants with per-quartet shuffled order (seed 2986799900, logged).
Single driver process, pgrep duplicate check at launch: exactly 1 instance
(recorded below). Concurrency 1, lane exclusive, latency not polluted.

## Results

160/160 turns, 0 HTTP errors, 0 duplicate cells. Interleave verified in the
EMITTED data: max same-variant run length in execution order = 2; every
aligned quartet covers all four variants (True). Single driver confirmed by
pgrep at launch (exactly 1 instance, no racing driver).

### 4-variant table (fired/40, per-task fired/10, depth = rtok est among fired)

| variant         | fired | math | code | reasoning | summary | depth med | depth mean |
|-----------------|-------|------|------|-----------|---------|-----------|------------|
| none            |  2/40 | 2    | 0    | 0         | 0       | 301       | 301        |
| suffix_identity | 17/40 | 10   | 7    | 0         | 0       | 573       | 681        |
| suffix_neutral  | 10/40 | 5    | 1    | 4         | 0       | 782.5     | 746        |
| suffix_topical  | 11/40 | 7    | 2    | 2         | 0       | 391       | 768        |

Fisher exact, two-sided, pooled per variant:

| comparison                  | counts        | p       |
|-----------------------------|---------------|---------|
| identity vs none            | 17/40 vs 2/40 | 0.00013 |
| neutral vs none             | 10/40 vs 2/40 | 0.025   |
| topical vs none             | 11/40 vs 2/40 | 0.013   |
| identity vs neutral         | 17/40 vs 10/40| 0.155   |
| identity vs topical         | 17/40 vs 11/40| 0.241   |
| neutral vs topical          | 10/40 vs 11/40| 1       |

Summary task never fires under any variant (0/10 across the board),
consistent with every prior study on this family.

### Cross-build comparison

| cell                    | NVFP4 (this run, interleaved) | hybrid 3.25bpw (blocked study) | p (cross-build) |
|-------------------------|-------------------------------|--------------------------------|-----------------|
| C6 no suffix            | 2/40                          | 5/40                           | 0.43            |
| C6 + identity suffix    | 17/40                         | 18/40                          | 1               |

The hybrid-lane interleaved 4-variant control (hybrid + Qwen) was still MID-RUN
at analysis time (118/160 and 150/160 rows on disk, drivers live); its
return has not landed, so per protocol this table compares against the
blocked identity-prefix study only. Cross-linking to that result
happens at land time, not here.

**Land-time addendum (packaging, 2026-07-27).** The hybrid interleaved
control has since landed (160/160, 0 errors): bare 0/40 vs identity 13/40 /
neutral 14/40 / topical 10/40, same verdict, position-generic, identity vs
neutral p = 1.0. The three-way cross-build table lives in
`../IDENTITY_PREFIX_STUDY_20260730.md` (section "NVFP4-build replication and
three-way convergence"); this report's numbers are unchanged.

### Same-build replication across sessions

This run's C6/none = 2/40 vs the ORIGINAL published NVFP4 gate-study C6 =
3/40: p=1. The C6 crater replicates cleanly on the same build across
sessions and serve cycles.

## Verdict

POSITION-GENERIC tail effect on the NVFP4 build. All three token-matched
suffixes significantly lift firing over bare C6 (p=0.00013 / 0.025 / 0.013).
The identity suffix has the highest point estimate (17/40 vs 10/40 and
11/40), but identity vs neutral (p=0.155) and identity vs topical (p=0.241)
are NOT significant at n=40: this run cannot claim an identity-specific
component beyond the generic effect. Nulls stated plainly: no significant
difference among the three suffix types; no significant drift of the base
C6 cell from the published 3/40.

Magnitude note (descriptive, not a significance claim): the identity-suffix
cell lands at 17/40 vs the hybrid's 18/40 and the no-suffix cell at 2/40 vs
5/40, so the tail-restoration magnitudes replicate across quant builds
almost exactly. Whether the identity-vs-filler gap (17 vs ~10) is a real
identity-specific increment is left open; deciding it at this effect size
needs roughly 3x the samples per cell.

## Provenance

- Driver: nvfp4_suffix_driver.py (this dir), stdout in driver_stdout.log
- Raw rows: logs/suffix_nvfp4.jsonl; order seed logs/order_seed_nvfp4.json;
  token counts logs/token_counts.json
- Template copy: nvfp4_serving_chat_template.jinja (md5 above)
- Analyzer: analyze_nvfp4_suffix.py
- Lane re-parked after run; fresh park marker with the exact restore recipe.
