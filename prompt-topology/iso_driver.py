#!/usr/bin/env python3
"""Ordering-isolation follow-up to the prompt-topology study — 2026-07-30 (fable).

The study's biggest finding: reversing requirement order inside the flowing-
prose paragraph flips bare Laguna firing 1/40 -> 15/40 (p=1.2e-4) while the
same reversal inside JSON does nothing. Mechanism unidentified. This runs the
single-requirement-swap design: move one requirement at a time instead of
reversing wholesale, testing the "which requirement sits nearest the task
boundary" hypothesis directly, plus the connective-free prose variant to
remove the last wording confound.

Scope: prose topology, BARE apparatus only (the flip is bare-only; C7
ordering deltas were ns), 4 gate-study tasks byte-identical, 10/cell, both
lanes (Qwen = null control). Single-turn throughout (§3a n/a). Same sampling,
ceiling, nonce discipline as the main study. Reuses chat/measure/log/TASKS
via import from prompt_topology_driver (no rewrite).

Conditions (prose renderings of the same 8 requirements):
  conn_orig     R1..R8           boundary=R8(word cap)   first=R1   [replication]
  conn_rev      R8..R1           boundary=R1(concise)    first=R8   [replication]
  conn_swapends R8,R2..R7,R1     boundary=R1             first=R8   interior original
  conn_r8first  R8,R1..R7        boundary=R7(code)       first=R8   R8 off boundary, R1 not on it
  conn_r1last   R2..R8,R1        boundary=R1             first=R2   R1 on boundary, first-slot ~original
  nocon_orig    R1..R8, no connectives
  nocon_rev     R8..R1, no connectives

If last-slot drives the flip: swapends ~= r1last ~= rev >> orig, and r8first
separates "R8 removed from boundary suffices" from "R1 at boundary required".
If first-slot drives it: swapends ~= r8first ~= rev, r1last ~= orig.
"""
import json, secrets, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prompt_topology_driver import (REQS, LEAD, CLOSE, TASKS, LANES, LOGS,
                                    chat, measure, log, note, tokenize)


def prose_seq(seq, connectives=True):
    parts = []
    for i, r in enumerate(seq):
        if connectives:
            conn = "You must " if i == 0 else "In addition, you must "
        else:
            conn = "You must "
        parts.append(conn + r + ".")
    return f"{LEAD} " + " ".join(parts) + f" {CLOSE}"


R = REQS  # R[0]..R[7] = R1..R8
CONDITIONS = {
    "conn_orig":     (list(R), True),
    "conn_rev":      (list(reversed(R)), True),
    "conn_swapends": ([R[7]] + R[1:7] + [R[0]], True),
    "conn_r8first":  ([R[7]] + R[0:7], True),
    "conn_r1last":   (R[1:8] + [R[0]], True),
    "nocon_orig":    (list(R), False),
    "nocon_rev":     (list(reversed(R)), False),
}


def build(cond):
    seq, conn = CONDITIONS[cond]
    return prose_seq(seq, conn)


def preflight():
    out = {}
    for lane in LANES:
        counts = {c: tokenize(lane, build(c)) for c in CONDITIONS}
        vals = list(counts.values())
        mean = sum(vals) / len(vals)
        out[lane] = {"counts": counts, "mean": round(mean, 1),
                     "band_lo": round(mean * 0.9, 1),
                     "band_hi": round(mean * 1.1, 1),
                     "all_in_band": all(mean * 0.9 <= v <= mean * 1.1 for v in vals)}
        note(f"{lane} iso blocks: {counts} mean={mean:.1f} "
             f"all_in_band={out[lane]['all_in_band']}")
    Path(__file__).resolve().parent.joinpath("iso_token_band.json").write_text(
        json.dumps(out, indent=1))
    return 0 if all(v["all_in_band"] for v in out.values()) else 2


def run_turn(logfile, lane, cond, task_type, idx):
    nonce = secrets.token_hex(4)
    messages = [{"role": "user",
                 "content": f"[run-{nonce}] {build(cond)}\n\n{TASKS[task_type]}"}]
    status, resp, lat = chat(lane, messages)
    row = {"lane": lane, "phase": "iso", "condition": cond,
           "task_type": task_type, "sample": idx, "nonce": nonce,
           "http_status": status, "latency_s": round(lat, 3),
           "latency_flag": "POLLUTED_shared_lane"}
    if status == 200:
        row.update(measure(resp))
    else:
        row["error"] = resp.get("error", "http_" + str(status))
    log(logfile, row)
    note(f"{lane} iso {cond} {task_type} {idx} ok={status == 200} "
         f"fired={row.get('thinking_fired')} fr={row.get('finish_reason')}")
    return row


def grid(lane):
    logfile = LOGS / f"iso_{lane}.jsonl"
    cells = [(c, t, i) for c in CONDITIONS for t in TASKS for i in range(10)]
    note(f"{lane} iso grid: {len(cells)} turns conc={LANES[lane]['conc']}")
    with ThreadPoolExecutor(max_workers=LANES[lane]["conc"]) as ex:
        futs = [ex.submit(run_turn, logfile, lane, c, t, i)
                for c, t, i in cells]
        for f in futs:
            f.result()
    note(f"{lane} iso COMPLETE")
    return 0


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "preflight":
        sys.exit(preflight())
    elif cmd == "grid":
        sys.exit(grid(sys.argv[2]))
    else:
        sys.exit("unknown phase")
