#!/usr/bin/env python3
"""Summarize the Qwen gate study logs: per-condition firing, per-task split,
finish-path classification, reasoning-token stats."""
import json, sys, statistics
from collections import Counter, defaultdict
from pathlib import Path

LOGS = Path.home() / "qwen_gate_study_20260728/logs"
TASKS = ["math", "code", "reasoning", "summary"]
CONDS = [f"C{i}" for i in range(10)]


def load(name):
    p = LOGS / name
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    return out


def ok(rows):
    return [r for r in rows if r.get("http_status") == 200]


def pct(a, b):
    return f"{round(100.0 * a / b)}%" if b else "-"


def main():
    pc = ok(load("parser_check.jsonl"))
    if pc:
        f = sum(1 for r in pc if r.get("thinking_fired"))
        print(f"=== PARSER CHECK (bare, no system prompt): {f}/{len(pc)} = {pct(f,len(pc))}")
        for t in TASKS:
            tr = [r for r in pc if r.get("task_type") == t]
            if tr:
                ff = sum(1 for r in tr if r.get("thinking_fired"))
                print(f"    {t:10s} {ff}/{len(tr)}  finish={dict(Counter(r.get('finish_reason') for r in tr))}")
        print()

    grid = ok(load("grid_turns.jsonl"))
    if grid:
        print("=== GRID: firing rate per condition (40 samples each) ===")
        hdr = f"{'cond':5s} {'fired':>9s} {'rate':>6s} | " + " ".join(f"{t[:4]:>5s}" for t in TASKS)
        print(hdr)
        print("-" * len(hdr))
        for c in CONDS:
            cr = [r for r in grid if r.get("condition") == c]
            if not cr:
                continue
            f = sum(1 for r in cr if r.get("thinking_fired"))
            cells = []
            for t in TASKS:
                tr = [r for r in cr if r.get("task_type") == t]
                ff = sum(1 for r in tr if r.get("thinking_fired"))
                cells.append(f"{ff}/{len(tr)}" if tr else "-")
            print(f"{c:5s} {f:>4d}/{len(cr):<4d} {pct(f,len(cr)):>6s} | " + " ".join(f"{x:>5s}" for x in cells))
        print()

        print("=== FINISH PATHS per condition (counts) ===")
        paths = sorted({r.get("finish_path") for r in grid if r.get("finish_path")})
        print(f"{'cond':5s} " + " ".join(f"{p.replace('reasoned','R').replace('no_think','N'):>22s}" for p in paths))
        for c in CONDS:
            cr = [r for r in grid if r.get("condition") == c]
            if not cr:
                continue
            cnt = Counter(r.get("finish_path") for r in cr)
            print(f"{c:5s} " + " ".join(f"{cnt.get(p,0):>22d}" for p in paths))
        print()

        print("=== reasoning tokens (est) on FIRED turns ===")
        for c in CONDS:
            cr = [r for r in grid if r.get("condition") == c and r.get("thinking_fired")]
            if not cr:
                print(f"{c:5s} (no fired turns)")
                continue
            toks = [r.get("thinking_tokens_est") or 0 for r in cr]
            comp = [r.get("completion_tokens") or 0 for r in cr]
            print(f"{c:5s} n={len(cr):>3d} median_rtok={int(statistics.median(toks)):>5d} "
                  f"mean_rtok={int(statistics.mean(toks)):>5d} max={max(toks):>5d} "
                  f"median_completion={int(statistics.median(comp)):>5d}")
        print()

        ceil = [r for r in grid if r.get("finish_reason") == "length"]
        print(f"=== ceiling hits (finish_reason=length): {len(ceil)}/{len(grid)} ===")
        if ceil:
            print("   by condition:", dict(Counter(r.get("condition") for r in ceil)))
            print("   by task:     ", dict(Counter(r.get("task_type") for r in ceil)))
        print()

    crit = ok(load("criteria_turns.jsonl"))
    if crit:
        print("=== CRITERIA-LOOP PROBE ===")
        for c in ["C0", "C4", "C7"]:
            cr = [r for r in crit if r.get("condition") == c]
            if not cr:
                continue
            f = sum(1 for r in cr if r.get("thinking_fired"))
            loops = sum(1 for r in cr
                        if r.get("finish_reason") == "length" and r.get("thinking_fired")
                        and (r.get("content_chars") or 0) == 0)
            print(f"{c:5s} fired={f}/{len(cr)} empty-content-ceiling loops={loops}/{len(cr)}")


if __name__ == "__main__":
    main()
