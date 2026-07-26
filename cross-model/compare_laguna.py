#!/usr/bin/env python3
"""Cross-model comparison: Laguna grid (2026-07-27) vs Qwen grid (2026-07-28).
Reads both studies' grid_turns.jsonl and prints a side-by-side firing table."""
import json
from pathlib import Path

STUDIES = {
    "Laguna S 2.1 NVFP4": Path.home() / "laguna_gate_study_20260727/logs/grid_turns.jsonl",
    "Qwen 3.6 35B-A3B": Path.home() / "qwen_gate_study_20260728/logs/grid_turns.jsonl",
}
TASKS = ["math", "code", "reasoning", "summary"]
CONDS = [f"C{i}" for i in range(10)]
LABELS = {
    "C0": "no system prompt",
    "C1": "helpful assistant",
    "C2": "coding assistant",
    "C3": "named helpful assistant",
    "C4": "named senior engineer (persona)",
    "C5": "persona + 3 style rules",
    "C6": "persona + 10 numbered rules",
    "C7": "full agent prompt + provenance",
    "C8": "C7 + tool schemas",
    "C9": "C7 + 'think step by step'",
}


def load(p):
    if not p.exists():
        return []
    rows = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("http_status") == 200:
            rows.append(r)
    return rows


def rate(rows, cond, task=None):
    sel = [r for r in rows if r.get("condition") == cond and (task is None or r.get("task_type") == task)]
    if not sel:
        return None, 0, 0
    f = sum(1 for r in sel if r.get("thinking_fired"))
    return round(100.0 * f / len(sel)), f, len(sel)


def main():
    data = {k: load(v) for k, v in STUDIES.items()}
    names = list(STUDIES)
    print("# Thinking-gate firing rate by system-prompt condition\n")
    w = 34
    print(f"{'cond':4s} {'condition':<{w}s} " + " ".join(f"{n:>22s}" for n in names))
    print("-" * (5 + w + 1 + 23 * len(names)))
    for c in CONDS:
        cells = []
        for n in names:
            pc, f, tot = rate(data[n], c)
            cells.append(f"{f}/{tot} ({pc}%)" if tot else "—")
        print(f"{c:4s} {LABELS[c]:<{w}s} " + " ".join(f"{x:>22s}" for x in cells))

    print("\n# Per-task firing (fired/total)\n")
    for n in names:
        rows = data[n]
        if not rows:
            continue
        print(f"## {n}")
        print(f"{'cond':5s} " + " ".join(f"{t:>12s}" for t in TASKS))
        for c in CONDS:
            cells = []
            for t in TASKS:
                pc, f, tot = rate(rows, c, t)
                cells.append(f"{f}/{tot}" if tot else "—")
            print(f"{c:5s} " + " ".join(f"{x:>12s}" for x in cells))
        print()


if __name__ == "__main__":
    main()
