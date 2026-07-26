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

---

## #1 — The reasoning field has two names

**The trap.** OpenAI-compatible servers expose the model's reasoning on either
`message.reasoning_content` or `message.reasoning`, and some expose only one.
A vLLM Qwen 3.6 NVFP4 lane has **no `reasoning_content` key at all**.

**The symptom.** Your firing rate reads **0%** while the model is visibly
reasoning. Worse, it reads 0% *consistently*, which looks like a clean finding
rather than a bug. Any harness that also uses reasoning length as a signal
silently loses that signal too.

**Where it bit.** Three separate times: our own vLLM/NVFP4 lane; a community
spine-probe runner whose reasoning column read 0 on all 42 rows; and a third
stack whose "0% fired" could not be distinguished from "was not parsed" until
the field was checked directly.

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

**Where it bit.** A 3.25bpw EXL3-tail hybrid container serving Laguna S 2.1
with the `poolside_v1` reasoning parser. Every single response.

**The check.** Assert that `content.lstrip()` does not start with `</think>`,
and that open and close tag counts in the response are balanced. In an
assembled prompt, expect exactly one dangling open `<think>` at the end (the
generation prompt) and treat any excess of closes as this trap.

**Found.** 2026-07-27, quant-floor verification of the hybrid quant.

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
Community-surfaced; we did not find it ourselves.

**Status.** Mechanism identified and a detector built (`preflight_template.py`
in the kit this registry ships with, which refuses to certify a lane whose
assembled history drops the marker). A **quantified stripped-versus-preserved
comparison is in progress**; this entry will be updated with the measured delta
when that lands. Until then, treat the mechanism as established and the
magnitude as unquantified.

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

## How to add an entry

Keep the five fields: trap, symptom, where it bit, the check, found-date. Lead
with the symptom a reader would actually observe, not the mechanism, because
people arrive here holding a weird number and no idea what caused it. Name the
stack and revision. If the trap produced a published number, say so, because
that is the part that tells a reader how much this class costs.
