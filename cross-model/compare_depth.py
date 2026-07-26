#!/usr/bin/env python3
"""Second-order cross-model comparison: if the gate does not close on Qwen,
does the SAME system-prompt dose still modulate reasoning LENGTH and the
ceiling-collapse rate? Compare against Laguna on the same axes."""
import json, statistics
from pathlib import Path

STUDIES = {
    "Laguna": Path.home() / "laguna_gate_study_20260727/logs",
    "Qwen": Path.home() / "qwen_gate_study_20260728/logs",
}
CONDS = [f"C{i}" for i in range(10)]


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


def main():
    print("# Fired-turn reasoning length + ceiling collapse, by condition\n")
    print(f"{'cond':5s} | " + " | ".join(
        f"{n} fire%  med_rtok  ceil%" for n in STUDIES))
    print("-" * 78)
    grids = {n: load(p / "grid_turns.jsonl") for n, p in STUDIES.items()}
    for c in CONDS:
        cells = []
        for n in STUDIES:
            rows = [r for r in grids[n] if r.get("condition") == c]
            if not rows:
                cells.append(f"{'—':>28s}")
                continue
            fired = [r for r in rows if r.get("thinking_fired")]
            firepct = round(100.0 * len(fired) / len(rows))
            ceil = sum(1 for r in rows if r.get("finish_reason") == "length")
            ceilpct = round(100.0 * ceil / len(rows))
            med = int(statistics.median([r.get("thinking_tokens_est") or 0 for r in fired])) if fired else 0
            cells.append(f"{firepct:>5d}%  {med:>8d}  {ceilpct:>4d}%")
        print(f"{c:5s} | " + " | ".join(cells))

    print("\n# Criteria-loop probe (empty-content ceiling loops)\n")
    for n, p in STUDIES.items():
        crit = load(p / "criteria_turns.jsonl")
        if not crit:
            print(f"{n}: (no criteria log)")
            continue
        print(f"## {n}")
        for c in ["C0", "C4", "C7"]:
            cr = [r for r in crit if r.get("condition") == c]
            if not cr:
                continue
            fired = sum(1 for r in cr if r.get("thinking_fired"))
            loops = sum(1 for r in cr
                        if r.get("finish_reason") == "length" and r.get("thinking_fired")
                        and (r.get("content_chars") or 0) == 0)
            print(f"  {c}: fired {fired}/{len(cr)}  empty-content loops {loops}/{len(cr)}")
        print()


if __name__ == "__main__":
    main()
