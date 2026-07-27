#!/usr/bin/env python3
"""Preserved-reasoning comparison arm — context-mass sweep addendum, 2026-07-29.

MECHANISM TEST requested by community lead. Template facts (verified live, see
reasoning_passthrough_test output in the writeup):
  - chat_template.jinja reads assistant-message `reasoning`/`reasoning_content`
    and renders it as <think>...</think> in prior turns when enable_thinking
    (or preserve_thinking) is true; clients that don't resend reasoning get an
    EMPTY <think></think> rendered on every prior assistant turn.
  - `preserve_thinking` kwarg exists (default false); it only matters when
    enable_thinking is false.
  - vLLM passes the field through (prompt_tokens 63 -> 303 with ~200-token
    reasoning attached; preserve_thinking=true renders it under thinking-off).

DESIGN: cells (d10,8K), (d20,8K), (d20,32K). One fresh history per cell built
exactly like the main sweep but CAPTURING each turn's reasoning. Then per cell:
  arm 'stripped'  : 10 probes against content-only history (sweep default —
                    prior turns render empty <think></think>)
  arm 'preserved' : 10 probes against the SAME history with each assistant
                    turn's actual reasoning attached (renders as real think
                    blocks; prompt mass grows accordingly — logged).
"""
import json, os, secrets, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, os.path.expanduser("results/context_mass_sweep_20260729"))
import context_mass_sweep_driver as d

OUT = Path(os.path.expanduser("results/context_mass_sweep_20260729"))
ARM_LOG = d.LOGS / "preserved_arm_turns.jsonl"
CELLS = [(10, 8000), (20, 8000), (20, 32000)]
PROBES = 10


def build_history_capturing(cell_id, depth, target_mass, docs, deep, diff):
    """Same steering as d.build_history but retains per-turn reasoning."""
    messages = [{"role": "system", "content": d.C7}]
    reasoning_by_index = {}   # index into messages -> reasoning str
    tokens_now = 0
    for turn in range(depth):
        remaining_turns = depth - turn
        per_turn = max(0, target_mass - tokens_now) / remaining_turns
        user_budget_chars = int(max(0, per_turn * 0.6) * 4)
        asst_budget_tok = int(max(24, min(700, per_turn * 0.4)))
        if user_budget_chars > 6000 and deep:
            prompt, src = d.deep_chunk_task(deep, user_budget_chars)
        elif user_budget_chars > 800 and docs:
            prompt, src = d.doc_chunk_task(docs, diff, user_budget_chars)
        elif per_turn > 120:
            prompt, src = d.rng.choice(d.STRUCTURED_FOLLOWUPS), {"src": "structured_followup"}
        else:
            prompt, src = d.rng.choice(d.SHORT_FOLLOWUPS), {"src": "short_followup"}
        nonce = secrets.token_hex(3)
        messages.append({"role": "user", "content": f"[h-{nonce}] {prompt}"})
        status, resp, lat = d.chat(messages, asst_budget_tok + 1500, thinking=True)
        content, reasoning = "", ""
        if status == 200:
            m = d.measure(resp)
            content = m.pop("_content")
            reasoning = ""
            ch = (resp.get("choices") or [{}])[0]
            msg = ch.get("message") or {}
            reasoning = msg.get("reasoning_content") or msg.get("reasoning") or ""
            tokens_now = (m["prompt_tokens"] or 0) + (m["completion_tokens"] or 0)
        if not content.strip():
            status2, resp2, _ = d.chat(messages, asst_budget_tok + 50, thinking=False)
            if status2 == 200:
                m2 = d.measure(resp2)
                content = m2.pop("_content")
                tokens_now = (m2["prompt_tokens"] or 0) + (m2["completion_tokens"] or 0)
        if not content.strip():
            content = "Acknowledged."
        messages.append({"role": "assistant", "content": content})
        reasoning_by_index[len(messages) - 1] = reasoning
        d.log(ARM_LOG, {"phase": "arm_history", "cell": cell_id, "turn": turn,
                        "http_status": status, "assistant_chars": len(content),
                        "reasoning_chars": len(reasoning),
                        "tokens_now_est": tokens_now, **src})
    return messages, reasoning_by_index, tokens_now


def probe(cell_id, depth, mass, arm, messages, idx):
    nonce = secrets.token_hex(4)
    msgs = messages + [{"role": "user", "content": f"[probe-{nonce}] {d.PROBE_TASK}"}]
    status, resp, lat = d.chat(msgs, d.PROBE_CEILING, thinking=True)
    row = {"phase": "arm_probe", "cell": cell_id, "depth": depth,
           "target_mass": mass, "arm": arm, "sample": idx, "nonce": nonce,
           "http_status": status, "latency_s": round(lat, 3)}
    if status == 200:
        m = d.measure(resp); m.pop("_content"); row.update(m)
    else:
        row["error"] = resp.get("error", f"http_{status}")
    d.log(ARM_LOG, row)
    return row


def main():
    d.note("preserved-reasoning arm start")
    docs, deep, diff = d.load_corpus()
    summary = {}
    for depth, mass in CELLS:
        cell_id = f"arm_d{depth}_m{mass//1000}k"
        t0 = time.time()
        messages, rmap, tok = build_history_capturing(cell_id, depth, mass, docs, deep, diff)
        captured = sum(1 for v in rmap.values() if v)
        d.note(f"{cell_id}: history built est_tokens={tok} "
               f"turns_with_reasoning={captured}/{len(rmap)} in {round(time.time()-t0)}s")
        stripped = messages
        preserved = [dict(m) for m in stripped]
        for i, r in rmap.items():
            if r:
                preserved[i]["reasoning"] = r
        cs = {}
        for arm, msgs in (("stripped", stripped), ("preserved", preserved)):
            with ThreadPoolExecutor(max_workers=d.PROBE_CONC) as ex:
                rows = list(ex.map(
                    lambda i: probe(cell_id, depth, mass, arm, msgs, i),
                    range(PROBES)))
            ok = [r for r in rows if r.get("http_status") == 200]
            fired = sum(1 for r in ok if r.get("thinking_fired"))
            pt = [r["prompt_tokens"] for r in ok if r.get("prompt_tokens")]
            cs[arm] = {"fired": fired, "n": len(ok),
                       "prompt_tokens_range": [min(pt), max(pt)] if pt else None}
            d.note(f"{cell_id} {arm}: fired {fired}/{len(ok)} pt={cs[arm]['prompt_tokens_range']}")
        summary[cell_id] = cs
    (OUT / "preserved_arm_summary.json").write_text(json.dumps(summary, indent=1))
    d.note("preserved-reasoning arm COMPLETE")


if __name__ == "__main__":
    main()
