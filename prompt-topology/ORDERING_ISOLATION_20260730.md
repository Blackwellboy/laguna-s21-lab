# Ordering isolation — single-requirement swaps + connective-free prose (2026-07-30)

Follow-up to `PROMPT_TOPOLOGY_STUDY_20260730.md`. Run date 2026-07-27 (UTC), same
lanes, same sampling/ceiling/nonce discipline, single-turn throughout (§3a n/a).
560 turns (7 conditions × 4 tasks × 10 × 2 lanes), **560/560 HTTP 200, zero
failed cells**. Raw: `logs/iso_{laguna,qwen}.jsonl`. All `latency_s` flagged
POLLUTED per-row (the identity-prefix study was still sharing both lanes).

## Question

The main study's biggest effect — reversing requirement order inside flowing
prose flips bare Laguna firing 1/40 → 15/40 (p=1.2e-4) — has an unidentified
mechanism. Hypothesis under test: **what sits nearest the task boundary (the
last slot) drives the flip.** Also: remove the connective confound (prose was
the one topology whose reversal reassigns "You must"/"In addition, you must"
to different requirements).

## Design

Prose topology, BARE apparatus only (the flip is bare-only; C7 ordering deltas
were ns). R1..R8 = the study's fixed requirement set.

| condition | order | boundary (last) | first | tests |
|---|---|---|---|---|
| conn_orig | R1..R8 | R8 (word cap) | R1 | replication |
| conn_rev | R8..R1 | R1 (concise) | R8 | replication |
| conn_swapends | R8,R2..R7,R1 | R1 | R8 | ends like rev, interior original |
| conn_r8first | R8,R1..R7 | R7 (code) | R8 | R8 off boundary without R1 on it |
| conn_r1last | R2..R8,R1 | R1 | R2 | R1 on boundary, first ~original |
| nocon_orig | R1..R8 | R8 | R1 | connective-free ("You must" every sentence) |
| nocon_rev | R8..R1 | R1 | R8 | connective-free reversal |

Token band: the five conn_* blocks are token-identical (153 Laguna / 154 Qwen —
perfect within-stratum control). The two nocon_* blocks are identical to each
other (132/133) but ~14% below the conn stratum — padding them would
reintroduce the wording confound the variant exists to remove, so per protocol
this is reported, not forced: **two internally-exact token strata; order
comparisons are only made within a stratum.** (`iso_token_band.json`.)

## Results — Laguna (fired/40; per-task fired/10 in raw and analyze output)

| condition | fired | rate | math | code | reasoning | summary |
|---|---|---|---|---|---|---|
| conn_orig | 7/40 | 17.5% | 6 | 1 | 0 | 0 |
| conn_rev | 12/40 | 30.0% | 8 | 4 | 0 | 0 |
| conn_swapends | 13/40 | 32.5% | 8 | 4 | 1 | 0 |
| conn_r8first | 11/40 | 27.5% | 8 | 3 | 0 | 0 |
| conn_r1last | 11/40 | 27.5% | 4 | 5 | 2 | 0 |
| nocon_orig | 4/40 | 10.0% | 2 | 2 | 0 | 0 |
| nocon_rev | 15/40 | 37.5% | 8 | 7 | 0 | 0 |

Key contrasts (two-sided Fisher):
- **nocon_orig 4/40 vs nocon_rev 15/40: p=0.0075** — the ordering effect
  replicates in the connective-free stratum, i.e. it is NOT a connective
  artifact (if anything it is stronger without connectives; nocon_rev exactly
  reproduces the main study's reversed-prose 15/40).
- conn_orig vs conn_rev: 7/40 vs 12/40, p=0.29 (ns in this run — see drift).
- conn_rev vs conn_swapends p=1.0; conn_rev vs conn_r1last p=1.0; conn_orig vs
  any single-swap condition: p=0.20–0.42 (all ns individually).

**Qwen: 280/280 fired, every condition and task.** The null control holds a
third time.

## Verdict on the boundary hypothesis

**Not supported.** All four perturbed conn orders — full reversal, swap-ends,
R8-first, R1-last — land in one indistinguishable band (27.5–32.5%),
regardless of which requirement occupies the task-boundary slot (R1, R7, or
R1 again) or the first slot (R8 or R2). No single position isolates the
effect. The better description of the data: **the original R1..R8 arrangement
is the suppressive pole, and any reordering away from it raises firing by a
similar amount** — a canonical-order effect, not a boundary-slot effect.
At n=40/condition the conn-stratum contrasts are individually ns; the claim
that survives at conventional significance is the connective-free pair.

## The replication caveat this run surfaced (important)

conn_orig fired **7/40 here vs 1/40 in the main grid** — byte-identical
prompts (nonce aside), same lane, same sampling, ~3.5 h apart (between-run
p≈0.057, driven by math: 0/10 → 6/10). Same-cell between-run drift at
temperature 0.7 is therefore comparable in size to some of the cell-level
effects the main study reports. Consequences, stated plainly:
- The main study's prose ordering flip stands as measured (1/40 vs 15/40,
  p=1.2e-4, contemporaneous cells), and its direction is confirmed here in
  the cleaner nocon stratum (p=0.0075).
- But its **magnitude is run-dependent**: today's conn-stratum gap is ~2×
  (17.5%→30%), not ~15×. Cell-level rates on this lane should be read with
  ±(several)/40 between-run noise, and any future single-cell claim under
  ~3× should be treated as unconfirmed until replicated in-run.
- Candidate sources: sampling stochasticity dominates (temp 0.7, small n);
  prefix-cache effects are nonce-defeated; concurrent lane load should not
  reach a prompt-determined gate (and Qwen's 100% wall confirms request
  handling was clean all day).

## Scope

n=40/condition, one requirement set, prose/bare only, one lane pair. The
identity-prefix study had not landed at time of writing; it probes the same
surface (prompt-surface features vs gate) — reconcile when it lands.

## Parked

- In-run A/B replication protocol (interleave conditions within one run) to
  kill between-run drift as a factor in all future gate comparisons.
- Larger-n conn-stratum rerun to resolve orig-vs-perturbed at significance.
- C7-apparatus isolation pass (json's 17→25 reversal hint).
