# Laguna S 2.1 thinking-gate suppression study — 2026-07-27

**Scope:** single-turn dose-response study of the thinking gate on poolside
Laguna S 2.1 NVFP4 **rev 0761412**, spark-host GB10, production serving profile
(vLLM 0.25.1 venv, DFlash K=7, max-num-seqs=32, poolside_v1 tool+reasoning
parsers, prefix caching + chunked prefill, FP8 KV, FLASHINFER, ctx 262144,
DEEP_GEMM=0 — cmdline verified flag-by-flag before any samples).
Single rev, single stack, n=40 per condition, single runs. Not a multi-rev or
multi-stack claim.

**Request shape (every turn):** `chat_template_kwargs.enable_thinking=true`,
`max_tokens=4096` (loop seatbelt), temperature 0.7, top_p 0.95, top_k 20.
Thinking fired = non-empty `reasoning_content` from the poolside_v1 parser.
Thinking tokens estimated as reasoning chars / 4. Every user prompt is
nonce-prefixed to defeat prefix-cache contamination across conditions.
450 logged turns total (20 parser check + 400 grid + 30 criteria), 0 HTTP
errors, run 2026-07-26 UTC (~5.6 h wall).

---

## 1. Parser caveat resolution (verdict up front)

The 12h soak's published caveat — "empty reasoning fields might be partly
template/parser-level" — is **resolved: the suppression was real.**

- 20 bare-prompt samples (no system message): **15/20 fired**, and every firing
  sample produced substantial parsed reasoning (median ~3.5K est. tokens).
  The template + poolside_v1 parser demonstrably CAN emit reasoning on this
  exact stack, so the soak's ~0.1% cannot be a parse failure.
- Divergence from the community "100% with no system prompt" report: firing was
  **task-conditional even bare** — math 5/5, code 5/5, multi-step reasoning
  5/5, **summarization 0/5**. Protocol tripped its <90% stop; template
  investigated before continuing (see `PARSER_CHECK_DIVERGENCE_REPORT.md`):
  our rev-0761412 template and Poolside's current HF template are
  mechanism-identical (`enable_thinking | default(true)`, open `<think>` at
  generation). Note the rev's default is TRUE — Tom's pinned config documented
  default false; consistent with his changelog note of post-release drift.
- The "492/492 (100%)" figure could not be located in canon or the offlabel
  page; the closest verified community datapoint is @Defilan's 6/6 bare vs 0/5
  persona. Treated as a reported figure, not a verified source.

## 2. The suppression curve (400 turns, 10 conditions × 4 tasks × 10)

| Cond | System prompt (dose) | Fired | math | code | reason | summ | med think-tok (fired) | ceiling hits |
|------|----------------------|-------|------|------|--------|------|--------------------|--------------|
| C0 | none | **30/40 (75%)** | 10/10 | 10/10 | 10/10 | 0/10 | 3536 | 29 |
| C1 | "helpful assistant" | 24/40 | 10/10 | 8/10 | 6/10 | 0/10 | 3154 | 21 |
| C2 | "coding assistant" | 16/40 | 10/10 | 6/10 | 0/10 | 0/10 | 2219 | 8 |
| C3 | named generic ("Alex, helpful") | 25/40 | 10/10 | 8/10 | 7/10 | 0/10 | 3069 | 23 |
| C4 | named professional ("Alex, senior staff engineer") | 18/40 | 10/10 | **0/10** | 8/10 | 0/10 | 2390 | 16 |
| C5 | professional + 3 rules | 9/40 | 9/10 | 0/10 | 0/10 | 0/10 | 1735 | 4 |
| C6 | professional + 10-rule block | **3/40 (7.5%)** | 3/10 | 0/10 | 0/10 | 0/10 | **325** | 0 |
| C7 | full agent prompt (no schemas) | 24/40 | 10/10 | 10/10 | 4/10 | 0/10 | **745** | 5 |
| C8 | C7 + real tool schemas | 29/40 | 10/10 | 10/10 | 9/10 | 0/10 | **282** | 2 |
| C9 | C7 + "think step by step" | 23/40 | 10/10 | 10/10 | 3/10 | 0/10 | 1028 | 5 |

(0 HTTP errors in all 400 turns. C8 additionally produced tool calls on 19/40
turns — schemas present made it act, including calling tools on math tasks.)

### Shape: not a single cliff — two axes

1. **Firing probability is a persona-and-task conjunction, non-monotonic in
   prompt length.** The deepest suppression is NOT the biggest prompt: the
   **10-rule instruction block (C6) suppresses hardest (3/40)**, far harder
   than the much longer full agent prompt (C7, 24/40). Dense behavioral
   instructions, not raw prompt mass, close the gate.
2. **Reasoning LENGTH collapses monotonically with dose even where firing
   stays high.** Median thinking tokens when fired: bare 3536 → agent prompt
   745 → agent+schemas 282. Under agent prompts the model still "thinks," but
   in short bursts that finish cleanly instead of running to the ceiling.
   Tom's "attenuation, not elimination, in agentic loops" is exactly this,
   visible single-turn.

### Per-task splits

- **Summarization: never fired once — 0/105 summarization attempts** (10 per
  grid condition x 10 conditions + 5 bare parser-check samples), under any
  condition including no system prompt. The strongest single suppressor found
  is the task itself.
- **Math is the most thinking-sticky task**: ≥9/10 in every condition except
  C6 (3/10).
- **Code is the persona-sensitive task**: 10/10 bare, **0/10 under the bare
  "senior staff engineer" persona (C4)** — reproducing Tom's zero — but back
  to 10/10 (short-burst) under the full agent prompt. So "coding-shaped tasks
  suppress regardless" refines to: code+persona gates hard, code+agent-prompt
  thinks briefly.

### Reconciling the three testers (hypothesis verdict)

Bare ~100% (non-summary tasks) → persona 5–18% → soak ~0.1% is **directionally
confirmed as a dose-response, with one honest gap**: our single-turn C7/C8
(soak-style prompts) fire 60–72%, not 0.1%. The soak's near-zero therefore
needs more than the system prompt — its turns carried large multi-turn
contexts (100K+ token document packs). **Context mass / conversation depth is
the likely remaining suppressor and is untested here** (future work:
firing-rate vs context-length sweep).

## 3. C9 verdict: explicit invitation does NOT override

"Think carefully step by step before answering" appended to the agent prompt:
**23/40 vs 24/40 baseline — no firing increase at all.** Median reasoning
length rose modestly (745 → 1028 est. tokens). If your harness needs thinking
back on this rev, a meta-instruction will not do it; the gate answers to
prompt *shape*, not stated intent.

## 4. Criteria-loop probe (30 turns, seatbelt 4096)

Task: a code function with six bulleted "Requirements / acceptance criteria."
Hard loop event = finish_reason=length AND reasoning non-empty AND **zero
content** (still inside the think block at the ceiling).

| Cond | Fired | length finishes | hard loops |
|------|-------|-----------------|------------|
| C0 bare | 1/10 | 1 | 1 |
| C4 persona | 1/10 | 1 | 1 |
| C7 agent prompt | **10/10** | 8 | **7** |

**The criteria-trigger report is confirmed, and it is a conjunction with the
agent prompt — an inversion of every other result.** Structured requirement
lists alone (bare or persona) mostly suppress thinking (1/10), like other
structured tasks. But under the full agent prompt — the exact condition that
elsewhere shortens thinking to ~745-token bursts — criteria lists flipped it
to 10/10 firing, and **7 of 10 turns ran reasoning to the 4096 ceiling and
never produced an answer** (verify-loop signature; one more truncated
mid-answer; two completed cleanly with ~880-token reasoning). Latencies
112–139 s per looping turn *with* the cap. Without a ceiling these are the
community's "it never stops" reports. **Suppression does not protect here —
the production-shaped prompt is the trigger's other half.**

## 5. What this means for operators (plain language)

- **The gate is not broken and not random.** It is a prompt-content dose
  response: what you put in the system prompt (and what kind of task you send)
  decides whether and how long the model thinks.
- **If you want thinking OFF** (recommended for agents on this rev): a dense
  instruction block (~10 rules) is the strongest single-prompt suppressor we
  measured, stronger than a persona line alone. Any realistic agent prompt
  already keeps thinking down to short bursts.
- **If you want thinking ON:** send no/minimal system prompt and a
  reasoning-shaped or math-shaped task. Asking it to "think step by step"
  under an agent prompt does not work. Summarization will not think, period.
- **The dangerous combination is thinking-on + agent prompt + bulleted
  acceptance criteria.** That flipped thinking to 100% and looped 70% of turns
  to the token ceiling with no answer. Since current uploads default thinking
  ON and ship no output cap: **pin your revision, keep enable_thinking off in
  agent pipelines, and always set your own max_tokens.** Criteria-driven
  prompting (which this model otherwise rewards) belongs with thinking off.
- **Budget note:** every thinking-on turn that fires hot costs ~80–140 s on a
  single Spark at 4096 cap, vs ~3–18 s suppressed.

## 6. Files

| File | Contents |
|------|----------|
| `gate_study_driver.py` | The exact driver (conditions, tasks, request shape) |
| `logs/parser_check.jsonl` | 20 bare-prompt turns |
| `logs/grid_turns.jsonl` | 400 grid turns (condition/task/sample/fired/tokens/latency/finish) |
| `logs/criteria_turns.jsonl` + `criteria_loop_events.jsonl` | 30 probe turns + loop flags |
| `summary.json` | Machine-readable aggregates |
| `PARSER_CHECK_DIVERGENCE_REPORT.md` | The mid-run stop, template comparison, resume decision |
| `driver_stdout.log` | Full run log |

**Credits:** TheTom (persona-suppression findings and the behavioral battery
this extends), @Defilan (bare-prompt firing + parser-population evidence on a
third stack), the community reporter of the criteria-loop behavior, and
poolside for the model.
