# Qwen thinking mechanism: verified BEFORE the grid (protocol step)

Date: 2026-07-26. Lane: spark-node-a :8100, `nvidia/Qwen3.6-35B-A3B-NVFP4` @ `491c2f1e`,
vLLM nightly with `--reasoning-parser qwen3`.

## How this model exposes the gate

On-disk `chat_template.jinja` (rev 491c2f1e), generation-prompt branch:

```jinja
{%- if enable_thinking is defined and enable_thinking is false %}
    {{- '<think>\n\n</think>\n\n' }}   {# pre-closed = suppressed #}
{%- else %}
    {{- '<think>\n' }}                 {# open = thinking invited #}
{%- endif %}
```

Same mechanism family as Laguna's `laguna_glm_thinking_v8` template
(open-`<think>` vs pre-closed-`</think>`), and like Laguna's rev it is
**on by default**: the suppression branch requires `enable_thinking` to be
explicitly *defined and false*; anything else (including omitting the kwarg)
takes the open-`<think>` branch.

## Response-field divergence (the thing that would have silently broken firing detection)

This lane does **not** return `reasoning_content`. That key is absent from the
message object entirely. Message keys observed:

```
['annotations', 'audio', 'content', 'function_call', 'reasoning', 'refusal', 'role', 'tool_calls']
```

Thinking arrives on **`message.reasoning`**. A detector written only against
`reasoning_content` would have scored every Qwen turn as "did not fire" and
produced a fake 0% curve. The Laguna driver's `measure()` already falls back to
`msg.get("reasoning")`, so the detection logic carried over unchanged, but the
field name is recorded here because the failure mode is silent.

## Live two-sided control (math task, max_tokens 4096)

| request | `reasoning` | content chars | completion tokens | finish |
|---|---|---|---|---|
| `enable_thinking: true` | **str, 6223 chars** | 901 | 2565 | stop |
| `enable_thinking: false` | **None** | 1577 | 511 | stop |

Both directions behave correctly: the kwarg controls the gate, the parser
populates the field when the gate opens, and the token accounting moves the
expected way (~2300 of 2565 completion tokens go to thinking when open; the
suppressed run answers directly in fewer total tokens).

**Conclusion: the gate mechanism and firing detection are sound on this stack.**
Any suppression curve measured below is a real content-dose effect, not a
template or parser artifact, the same conclusion the Laguna study reached for
its own stack, established here independently before collecting grid data.

## Note on token accounting

This lane's `usage` block has no `reasoning_tokens` / `thinking_tokens` field
(keys: `prompt_tokens`, `total_tokens`, `completion_tokens`,
`prompt_tokens_details`). The driver therefore keeps the Laguna-comparable
`len(reasoning)//4` estimate and additionally records `completion_tokens` and
`content_chars` so the reasoning/answer split stays derivable per turn.
