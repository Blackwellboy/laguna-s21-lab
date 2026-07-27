# Known template traps

A running registry of chat-template and serving-path failures that produce
**confidently wrong measurements**. Every entry here was found the expensive
way, usually after a number had already been published or shared.

The common shape: the request looks correct, the response looks correct, and
the number is still wrong, because something happened between the two that
nobody inspected. Request-shaped checks cannot catch any of these.

Each entry gives you the trap, the symptom it produces, where it bit, the check
that catches it, and when it was found. If you run one check from this file,
make it the one for trap #4, because it is the only one whose symptom looks
like a genuine model property rather than a bug.

**Scope note.** These were found while characterizing a handful of models on
DGX Spark class hardware across vLLM, llama.cpp, and an EXL3-tail container.
Trap #1 and #4 are template/serving-path classes and should be assumed present
elsewhere until checked. The specific model revisions are named so you can tell
"this was true of that checkpoint" from "this is true of the family".

**Build scoping (added 2026-07-30).** Revision alone is not enough. Thinking
policy differs by **build**, not just revision: FP8 and NVFP4 uploads of the
same model behave differently on the wire (@quantumleap68 measured the FP8
build skipping trivial follow-up turns under every prompt tried, including a
byte-exact replay of a known-good client request shape at 1/6, while the NVFP4
build reasons essentially every turn). A published firing rate that names a
revision without its build is underspecified. State **build AND revision**
next to every number, and treat cross-build comparisons as cross-model until
shown otherwise.

---

## #1 — The reasoning field has two names

**The trap.** OpenAI-compatible servers expose the model's reasoning on either
`message.reasoning_content` or `message.reasoning`, and some expose only one.
A vLLM Qwen 3.6 NVFP4 lane has **no `reasoning_content` key at all**.

**The symptom.** Your firing rate reads **0%** while the model is visibly
reasoning. Worse, it reads 0% *consistently*, which looks like a clean finding
rather than a bug. Any harness that also uses reasoning length as a signal
silently loses that signal too.

**Where it bit.** Five surfaces across three separate tools. Our own vLLM/NVFP4
lane; a community spine-probe runner whose reasoning column read 0 on all 42
rows; a third stack whose "0% fired" could not be distinguished from "was not
parsed" until the field was checked directly; and then, after that was fixed,
**two thinking-probe scripts in the same upstream toolkit that still read only
the one field**. Those two are the sharpest case, because their entire job is to
measure whether a model reasons: on a vLLM lane one would have reported
`NO_REASONING` in every arm, and the other would have shown a persona gate as
perfectly effective *including in its own control cell*. Both are fabricated
results that look like findings.

The generalisation worth carrying: this is not a bug that happened to some
scripts, it is a property of **any tool that reads a reasoning field**. Audit all
of them at once, not the one that surfaced the problem.

**The check.** Read **both** keys, and fall back to scraping `<think>` tags out
of `content`:

```python
reasoning = msg.get("reasoning_content") or msg.get("reasoning") or ""
```

Then confirm positively: send one prompt you are confident makes the model
think, and assert the field is non-empty. An empty field means *wrong key* at
least as often as it means *did not reason*.

**Found.** 2026-07-26, cross-model gate study and spine-probe runs.

---

## #2 — Orphaned `</think>` leaking into content

**The trap.** A reasoning parser that strips the opening `<think>` but not the
closing tag. Every response arrives with a stray `</think>` at the very start of
`content`.

**The symptom.** Content corruption that renders fine in a chat window and
breaks everything downstream: prefix matching, JSON extraction, first-line
parsing, diffing. It also inflates or deflates content-length metrics by a
constant, which is the kind of error that survives review because it looks like
a small consistent offset.

**Where it bit.** First seen on a 3.25bpw EXL3-tail hybrid container serving
Laguna S 2.1 with the `poolside_v1` reasoning parser — every single response —
and initially attributed to that container's configuration. **That attribution
was wrong.** The full-precision spine run (2026-07-28,
`spine-probes/fullprecision/`) reproduced it on a venv-serve vLLM 0.25.1 lane
with the same parser: it is `poolside_v1`-on-vLLM behaviour, triggered whenever
the `enable_thinking` kwarg is **absent** and the model emits an empty think
block (absent = ON on this revision, but low-firing task shapes skip thinking).
The parser strips the empty block's opening but leaves the orphan close.

**The check.** Assert that `content.lstrip()` does not start with `</think>`,
and that open and close tag counts in the response are balanced. In an
assembled prompt, expect exactly one dangling open `<think>` at the end (the
generation prompt) and treat any excess of closes as this trap.

**The fix.** Send `enable_thinking` explicitly, either value. With the kwarg
explicit the artifact appeared in 0/984 A/B rows (`pr10-replication/`); with it
absent, in 42/42 non-firing spine rows on both serving stacks.

**Found.** 2026-07-27, quant-floor verification of the hybrid quant.
Re-attributed 2026-07-28 after the full-precision reproduction.

---

## #3 — `enable_thinking` default drifts between revisions

**The trap.** The same model family ships templates whose default for the
thinking kwarg differs by revision and by upload. One checkpoint defaults it to
`true`; another tester's pin documents `false`. Separately, some servers supply
the kwarg themselves, so the template's `| default(...)` branch never runs and
**omitting the kwarg is not the same as passing its default**.

**The symptom.** Two testers say "same model" and get materially different
behavior, then spend a week reconciling numbers that were never comparable.
Bug reports land against the model that are really config drift.

**The check.** Never reason about thinking from a template's default. Send the
kwarg **explicitly**, and render your own prompt to confirm which branch you
landed in. Record the checkpoint revision hash next to every published number.

**Found.** 2026-07-25 to 2026-07-26, reconciling three independent stacks.
Rev `0761412` defaults `enable_thinking` to `true`; another pinned fork
documented `false`.

---

## #4 — Prior-turn reasoning stripped from history, and the model reads it

**This is the most dangerous entry in this file.** Its symptom is not a broken
parse or a corrupted string. Its symptom is a *plausible, publishable, wrong
finding about model behavior*.

**The trap.** With thinking enabled, the template renders prior assistant turns
into the history **without** their reasoning, emitting an empty `<think></think>`
block where the reasoning used to be, unless the reasoning is explicitly resent
and preserved. The model then reads its own history as evidence that it does not
think here, and suppresses accordingly. The control is a **`preserve_thinking`**
kwarg that the template reads and **the model card does not document**.

**The symptom.** Thinking fires normally at single turn and collapses toward
zero as the conversation deepens. It looks exactly like a genuine, interesting
property of the model. We measured **60 to 72% firing single-turn** against
**~0.1% across a 12-hour multi-turn soak** (3 of 3,096 turns) and spent real
effort theorizing about "context mass" and "turn depth" as the mechanism. The
mechanism was the template.

**Where it bit.** Our 12h production soak on Laguna S 2.1 NVFP4 / vLLM. Four
independent testers characterized this model and **all four missed it**, because
every check anyone ran was request-shaped: correct kwargs, correct response
parsing, correct field names. Nobody dumped the assembled prompt at turn N.
Community-surfaced — the lead was @quantumleap68's; we did not find it
ourselves.

**Status.** **Mechanism confirmed and quantified (2026-07-29,
`context-mass/`).** Identical transcripts probed with prior-turn reasoning
stripped vs resent: **0/10 vs 10/10 firing at depth 10 / ~8K tokens, and 0/10
vs 10/10 at depth 20 / ~8K** (3.25bpw hybrid lane; 45% single-turn baseline).
The surrounding 15-cell depth×mass sweep — all client-default stripped
histories — fired 0/150 with flat-zero curves on both axes, so depth and mass
are epiphenomenal to the stripping. **The fix:** resend `reasoning` on prior
assistant messages (with thinking on, the template then renders the real think
blocks; verified passthrough moves prompt_tokens accordingly), or set
`preserve_thinking: true` for thinking-off flows. Cost ~250-320 prompt tokens per
preserved turn that carries reasoning (measured: +1,615 prompt tokens over 5 preserved turns at d10, +4,764 over 19 at d20). Partial preservation suffices at moderate
depth (the d10 history carried reasoning on only 5/10 turns and still
recovered 10/10). A detector ships with this registry's kit
(`preflight_template.py`, which refuses to certify a lane whose assembled
history drops the marker). One measurement note for anyone replicating: a
session cannot bootstrap its own preserved history — once the gate closes at
turn 2, live-accumulated turns contain no reasoning to preserve (our first arm
was vacuous exactly this way, 0/50 turns; kept in the raw logs) — generate
history turns statelessly. NVFP4 confirmation on the production lane pending.
Raw + writeup: `context-mass/`. Still community-surfaced — @quantumleap68's
lead; we did not find the kwarg ourselves.

**Independently confirmed on a second stack and client (2026-07-30,
@quantumleap68).** Wire-level measurement (Hermes CLI → vLLM 0.25.1, Laguna
NVFP4 TP=1 and FP8 TP=2, a logging proxy between client and server, N≥6 per
cell, all claims read off the wire): a client that strips reasoning from
replayed history renders each prior turn as an empty `<think></think>`, and
the collapse tracks turn-by-turn — **turn 1: 199 reasoning deltas; turns 2 and
3 with stripped history: none**. Same mechanism, different client and serving
pair, measured at the transport layer rather than the log layer. His
client-side fix pattern is the right shape for tooling authors: **opt
providers into echoing reasoning on replay** via an explicit per-provider
capability flag, rather than vendor-sniffing which models need it.

**The check.** Assemble a three-turn conversation whose first assistant message
carries a uniquely-marked reasoning string, render the actual prompt through
your serving path, and grep it for that marker. If it is absent, your multi-turn
numbers describe a model that cannot see its own thinking. Then diff the render
with and without the preservation kwarg. `preflight_template.py` in this kit
does exactly this and refuses to pass the lane if the marker is missing.

Corollary worth internalizing: **enumerate every kwarg the template reads and
diff it against the model card.** Anything read-but-undocumented is an untested
variable, and if it sits near a thinking branch, assume it changes your results
until you have shown it does not.

**Found.** 2026-07-27, after the gate study published.

---

## #5 — A scoring detail silently flips a verdict

Traps #1–#4 corrupt what the model *receives* or what you *read back*.
This one corrupts what your scorer *decides*, which is worse in one specific way:
it leaves no trace in the raw logs at all. The transcript is fine. The number is
wrong.

**The trap.** A scoring or parsing detail that normalizes differently from the
text it is scoring. Unicode punctuation is the common one: a matcher written with
a straight apostrophe (`'`) does not match a model that emitted a curly one
(`’`). Same class: smart quotes, non-breaking spaces, collapsed whitespace,
en-dash versus hyphen, and any regex assuming ASCII against a model that emits
typographic characters.

**The symptom.** Verdicts that flip on characters nobody looked at. A clean
refusal scored as compliance, or a fold scored as a hold. The tell is that the
classifier's counts do not survive a hand-read of the same transcripts, and the
disagreements cluster on responses that "look fine" to a human reader. Because
the underlying text is unchanged, no amount of re-reading the raw logs shows you
anything wrong.

**Where it bit.** An upstream behavioral checker, in exactly the way that makes
the point: a response reading "I can't omit the PII" used a curly apostrophe, the
checker matched only the straight one, and a clean hold was briefly scored as a
silent fold. The detail that matters is that this happened **inside a script
written specifically to catch an earlier classifier failure**. The tool built to
catch the bug had the bug. Caught and corrected by its author before the numbers
were published.

**The check.** Two parts, and the second is not optional:

1. **Normalize before matching.** `unicodedata.normalize("NFKC", text)` plus an
   explicit fold of typographic punctuation to ASCII, applied to both the pattern
   and the text. Assume any model can emit smart quotes, because they do.
2. **Hand-read a sample of every borderline verdict**, especially the `UNCLEAR`
   and near-threshold bucket. A classifier's agreement with itself proves
   nothing. This is the same lesson as trap #4 from a different direction: the
   check that cannot fail is not a check.

If a scored result is going to be published, the hand-read step is the difference
between a number and a claim.

**Found.** 2026-07-29, during a cross-checked fold-count correction.

---

## #6 — Identity-sentence eviction: the thinking gate keys on the literal first line

**The trap.** The template's trained identity sentence — the default
"You are …" line the model was trained to see first — acts as a **pure prefix
key** for the thinking gate. Replace it with your own system prompt and the
gate closes; the content of your prompt barely matters, its *position* does.

**The symptom.** Thinking collapses under any real system prompt, and no
amount of instruction tuning brings it back — appending "always think",
raising verbosity, or rewording the prompt does nothing. It looks exactly like
generic prompt-dose suppression, so you tune the prompt harder and measure the
same zero.

**Where it bit.** @quantumleap68's wire-level battery (Hermes CLI → vLLM
0.25.1, Laguna NVFP4 TP=1 and FP8 TP=2, logging proxy, N≥6 per cell). His
measured cells: no system message **8/8** fired · "You are a helpful
assistant." **6/6** · full 40K agent prompt **0/8** · the same 40K prompt with
the identity sentence prepended as the literal first line **6–7/8** · identity
appended at the **end** of the prompt **0/8** · identity spliced mid-sentence
**1/6** · identity intact as line one plus a sentence after it **4/6**. A pure
prefix prior: presence is not enough, position is the variable.

**The check.** Prepend the template's own default identity sentence as the
literal first line of your system message and re-measure firing. If the rate
recovers, you were looking at identity eviction, not instruction-dose
suppression — and every "prompt dose" number you took without controlling the
first line is confounded.

**Status.** Sourced from @quantumleap68's measurements. Independently under
test on our stack (a study is running as of this entry); our result is not yet
in.

**Found.** 2026-07-30, reported by @quantumleap68 from wire-level measurement.

---

## #7 — `reasoning_effort` accepted and silently ignored

**The trap.** The request schema accepts a `reasoning_effort` parameter, the
server returns 200, and the chat template has **no handling for it at all**.
The parameter parses, validates, and does nothing.

**The symptom.** Effort levels change nothing — identical reasoning depth at
`low`, `medium`, and `high` — and you conclude the model ignores depth
requests, or worse, publish a "reasoning_effort has no effect on this model"
finding as if it had been exercised. On templates like this, prompting is the
only depth lever that exists.

**Where it bit.** @quantumleap68's wire-level battery on Laguna (Hermes CLI →
vLLM 0.25.1): `reasoning_effort` is a no-op because the template never reads
it. Same class as trap #4's corollary in reverse — there, the template read a
kwarg the model card didn't document; here, the API accepts a parameter the
template doesn't read. Both directions of the schema/template mismatch produce
silent wrong numbers.

**The check.** Grep the chat template for the parameter name **before**
trusting any knob you send. If the template never references it, the knob is
dead on this build regardless of what the server accepts. The trap #4
corollary generalizes to: diff the set of kwargs the template reads against
the set the API accepts, in both directions.

**Found.** 2026-07-30, reported by @quantumleap68 from wire-level measurement.

---

## How to add an entry

Keep the five fields: trap, symptom, where it bit, the check, found-date. Lead
with the symptom a reader would actually observe, not the mechanism, because
people arrive here holding a weird number and no idea what caused it. Name the
stack and revision. If the trap produced a published number, say so, because
that is the part that tells a reader how much this class costs.
