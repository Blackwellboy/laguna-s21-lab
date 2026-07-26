# Parser-check divergence report — written BEFORE grid continuation (per protocol)

Date: 2026-07-26 (study folder dated 20260727)
Status: divergence investigated; grid resumed with the finding documented.

## What happened

Bare-prompt parser check (20 samples, no system message, enable_thinking=true,
max_tokens=4096): **fired 15/20 (75%)** — below the ~100% expected from the
community no-system-prompt report, tripping the protocol stop.

Per-task split:

| task | fired |
|------|-------|
| math | 5/5 |
| code | 5/5 |
| reasoning | 5/5 |
| summarization | **0/5** |

All 15 firing samples ran reasoning to the 4096 ceiling (finish=length).
All 5 summarization samples returned clean, well-formed summaries with
`finish=stop` and empty reasoning.

## Template investigation (protocol step)

1. **On-disk rev-0761412 template** (`chat_template.jinja` in the model dir):
   `enable_thinking = enable_thinking | default(true)`; generation prompt emits
   `<assistant><think>` when true, `<assistant></think>` when false.
2. **Poolside current HF template** (poolside/Laguna-S-2.1 main, fetched live):
   IDENTICAL mechanism — same default(true), same open-`<think>`/pre-closed-
   `</think>` branches (header comment `laguna_glm_thinking_v8`).
3. Note vs TheTom's offlabel guide: his pin (~2026-07-24, GGUF/llama.cpp)
   documented `default(false)`; both our rev and Poolside current are
   `default(true)` — consistent with his changelog note that Poolside flipped
   thinking on-by-default post-release.

## Verdict

- **The template/parser CANNOT be the cause of low firing on this stack**: with
  the open `<think>` handed to it, the model produced substantial parsed
  reasoning in 15/20 bare samples. The poolside_v1 reasoning parser populates
  `reasoning_content` correctly.
- **Therefore the 12h soak's ~0.1% firing rate was REAL suppression** (system-
  prompt-driven), not a template/parser artifact. The published caveat is
  resolved in favor of real suppression.
- The 75% (not ~100%) is a **task-shaped gate effect on bare prompts**:
  summarization alone fully suppressed thinking with no system prompt at all.
  This does not match the "100% with no system prompt" community figure as a
  universal; it matches it only for math/code/reasoning-shaped tasks. (The
  492/492 figure itself could not be located in canon or the offlabel page;
  closest verified community datapoint is @Defilan's 6/6 bare vs 0/5 persona.)

## Decision

Grid resumed (SKIP_PARSER=1) because the stop-condition's target — parser or
template divergence — is affirmatively ruled out, and the residual divergence
is exactly the kind of content-dose effect the grid is designed to measure.
Flagged here rather than silently absorbed; if the operator prefers the strict
reading (halt on any sub-100%), the grid data past this point is separable by
phase field in the JSONL.
