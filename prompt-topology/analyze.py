#!/usr/bin/env python3
"""Analysis for the prompt-topology study — firing by topology x apparatus x
task per lane, token-band table, ordering comparison, finish paths."""
import json, sys
from collections import defaultdict
from pathlib import Path

OUT = Path(__file__).resolve().parent
LOGS = OUT / "logs"


def load(path):
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text().splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return rows


def cellkey(r):
    return (r["topology"], r["order"], r["apparatus"], r["task_type"])


def tab(rows, label):
    cells = defaultdict(lambda: {"n": 0, "fired": 0, "err": 0, "rtok": [],
                                 "ceil": 0, "paths": defaultdict(int)})
    for r in rows:
        c = cells[cellkey(r)]
        if r.get("http_status") != 200:
            c["err"] += 1
            continue
        c["n"] += 1
        if r.get("thinking_fired"):
            c["fired"] += 1
            c["rtok"].append(r.get("thinking_tokens_est") or 0)
        if r.get("finish_reason") == "length":
            c["ceil"] += 1
        c["paths"][r.get("finish_path", "?")] += 1
    print(f"\n== {label} ==")
    print(f"{'topology':10} {'order':9} {'app':5} {'task':10} "
          f"{'fired':>7} {'medrtok':>8} {'ceil':>5} {'err':>4}  paths")
    for k in sorted(cells):
        c = cells[k]
        rt = sorted(c["rtok"])
        med = rt[len(rt) // 2] if rt else 0
        paths = ",".join(f"{p}:{n}" for p, n in sorted(c["paths"].items()))
        print(f"{k[0]:10} {k[1]:9} {k[2]:5} {k[3]:10} "
              f"{c['fired']:>3}/{c['n']:<3} {med:>8} {c['ceil']:>5} "
              f"{c['err']:>4}  {paths}")
    # per topology x apparatus rollup
    roll = defaultdict(lambda: [0, 0])
    for k, c in cells.items():
        r = roll[(k[0], k[1], k[2])]
        r[0] += c["fired"]
        r[1] += c["n"]
    print("-- rollup (topology/order/apparatus) --")
    for k in sorted(roll):
        f, n = roll[k]
        pct = 100 * f / n if n else 0
        print(f"{k[0]:10} {k[1]:9} {k[2]:5} {f:>3}/{n:<3} {pct:5.1f}%")
    return cells


def main():
    for lane in ("laguna", "qwen"):
        rows = load(LOGS / f"grid_{lane}.jsonl") + load(LOGS / f"order_{lane}.jsonl")
        if rows:
            tab(rows, lane)
        # prompt-token verification per topology (actual usage)
        pt = defaultdict(list)
        for r in rows:
            if r.get("prompt_tokens"):
                pt[(r["topology"], r["apparatus"])].append(r["prompt_tokens"])
        if pt:
            print(f"-- {lane} actual prompt_tokens (mean over cells) --")
            for k in sorted(pt):
                v = pt[k]
                print(f"{k[0]:10} {k[1]:5} mean={sum(v)/len(v):7.1f} "
                      f"min={min(v)} max={max(v)} n={len(v)}")


if __name__ == "__main__":
    main()
