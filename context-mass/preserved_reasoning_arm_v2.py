#!/usr/bin/env python3
"""Preserved-reasoning arm v2 — stateless history generation, 2026-07-29.

WHY v2: arm v1 built histories by live accumulation, but the gate closes from
turn 2 of any session, so 0/50 history turns produced reasoning and the
'preserved' arm had nothing to preserve (verified: identical prompt_tokens).
v2 generates each assistant history turn STATELESSLY — [C7, that user turn]
only, where single-turn firing is ~45% overall and 10/10 on code tasks —
retrying up to 5x until thinking fires. The turns are then assembled into one
multi-turn transcript per cell. DOCUMENTED DEVIATION: history turns are
independent single-turn generations, not an accumulated session; that is the
point — it is the only way (on this lane) to hold transcript text fixed while
varying whether prior-turn reasoning is present in context.

Cells: (d10, 8K) and (d20, 8K). Arms per cell, same assembled transcript:
  stripped  : assistant turns content-only (prior turns render <think></think>)
  preserved : assistant turns with their real captured reasoning attached
              (prior turns render full think blocks; prompt mass grows — the
              sweep already showed stripped firing is 0/10 at ALL masses
              2K-32K, so added mass cannot explain any recovery).
10 probes per arm (same nonce-prefixed gate-study reasoning task).
"""
import json, os, secrets, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, os.path.expanduser("results/context_mass_sweep_20260729"))
import context_mass_sweep_driver as d

OUT = Path(os.path.expanduser("results/context_mass_sweep_20260729"))
LOG = d.LOGS / "preserved_arm_v2_turns.jsonl"
CELLS = [(10, 8000), (20, 8000)]
PROBES = 10
RETRIES = 5

FUNC_SPECS = [
    "Write a Python function flatten(nested) that flattens arbitrarily nested lists into one flat list, iteratively (no recursion). Include two example calls.",
    "Write a Python function rle_encode(s) producing run-length encoding pairs and rle_decode(pairs) inverting it. Include a round-trip example.",
    "Write a Python function top_k_frequent(words, k) returning the k most frequent words, ties broken alphabetically. Include one example.",
    "Write a Python function parse_semver(s) splitting 'MAJOR.MINOR.PATCH-PRERELEASE+BUILD' into a dict, raising ValueError on malformed input. Two examples.",
    "Write a Python function moving_average(xs, w) returning the sliding-window mean as a list of floats; raise ValueError if w<1 or w>len(xs). One example.",
    "Write a Python function dedupe_stable(items, key=None) removing duplicates while preserving first-seen order, optional key function. Two examples.",
    "Write a Python function balanced(s) checking balanced brackets ()[]{} ignoring other chars, returning bool. Three examples.",
    "Write a Python function chunk(iterable, n) yielding lists of size n (last may be short); n<1 raises ValueError. One example.",
    "Write a Python function invert_index(docs) mapping each word to the sorted list of doc ids containing it, given {doc_id: text}. One example.",
    "Write a Python function roman(n) converting 1..3999 to Roman numerals, raising ValueError outside range. Three examples.",
]


def gen_turn_stateless(cell_id, turn, user_budget_chars, docs, diff):
    """One code-shaped user turn + stateless assistant gen with fired thinking."""
    if user_budget_chars > 900 and diff.exists() and turn % 2 == 0:
        body = diff.read_text(encoding="utf-8", errors="replace")
        start = (turn * 977) % max(1, len(body) - user_budget_chars)
        prompt = ("Code review this diff excerpt. List bugs, missing tests, and risk.\n\n"
                  + body[start:start + user_budget_chars])
        src = {"src": "code_diff_sample.patch", "chars": user_budget_chars}
    else:
        prompt = FUNC_SPECS[turn % len(FUNC_SPECS)]
        src = {"src": "func_spec", "spec_idx": turn % len(FUNC_SPECS)}
    nonce = secrets.token_hex(3)
    user_msg = {"role": "user", "content": f"[h-{nonce}] {prompt}"}
    for attempt in range(RETRIES):
        status, resp, lat = d.chat(
            [{"role": "system", "content": d.C7}, user_msg], 2200, thinking=True)
        if status != 200:
            continue
        m = d.measure(resp)
        content = m.pop("_content")
        msg = (resp.get("choices") or [{}])[0].get("message") or {}
        reasoning = msg.get("reasoning_content") or msg.get("reasoning") or ""
        if reasoning and content.strip():
            d.log(LOG, {"phase": "v2_history", "cell": cell_id, "turn": turn,
                        "attempt": attempt, "fired": True,
                        "reasoning_chars": len(reasoning),
                        "assistant_chars": len(content), **src})
            return user_msg, content, reasoning
    d.log(LOG, {"phase": "v2_history", "cell": cell_id, "turn": turn,
                "fired": False, "gave_up_after": RETRIES, **src})
    return user_msg, (content if status == 200 and content.strip() else "Acknowledged."), ""


def probe(cell_id, depth, mass, arm, messages, idx):
    nonce = secrets.token_hex(4)
    msgs = messages + [{"role": "user", "content": f"[probe-{nonce}] {d.PROBE_TASK}"}]
    status, resp, lat = d.chat(msgs, d.PROBE_CEILING, thinking=True)
    row = {"phase": "v2_probe", "cell": cell_id, "depth": depth,
           "target_mass": mass, "arm": arm, "sample": idx, "nonce": nonce,
           "http_status": status, "latency_s": round(lat, 3)}
    if status == 200:
        m = d.measure(resp); m.pop("_content"); row.update(m)
    else:
        row["error"] = resp.get("error", f"http_{status}")
    d.log(LOG, row)
    return row


def main():
    d.note("preserved-reasoning arm v2 start (stateless history gen)")
    docs, deep, diff = d.load_corpus()
    summary = {}
    for depth, mass in CELLS:
        cell_id = f"v2_d{depth}_m{mass//1000}k"
        per_turn_chars = int(mass / depth * 0.55 * 4)   # user-side steering
        t0 = time.time()
        with ThreadPoolExecutor(max_workers=4) as ex:
            triples = list(ex.map(
                lambda t: gen_turn_stateless(cell_id, t, per_turn_chars, docs, diff),
                range(depth)))
        captured = sum(1 for _, _, r in triples if r)
        stripped = [{"role": "system", "content": d.C7}]
        preserved = [{"role": "system", "content": d.C7}]
        for user_msg, content, reasoning in triples:
            stripped += [user_msg, {"role": "assistant", "content": content}]
            a = {"role": "assistant", "content": content}
            if reasoning:
                a = dict(a); a["reasoning"] = reasoning
            preserved += [user_msg, a]
        d.note(f"{cell_id}: {depth} turns assembled, reasoning captured "
               f"{captured}/{depth}, in {round(time.time()-t0)}s")
        cs = {"turns_with_reasoning": captured, "depth": depth}
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
    (OUT / "preserved_arm_v2_summary.json").write_text(json.dumps(summary, indent=1))
    d.note("preserved-reasoning arm v2 COMPLETE")


if __name__ == "__main__":
    main()
