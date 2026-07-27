#!/usr/bin/env python3
"""Summarize identity-prefix grids into per-cell tables."""
import json, sys
from collections import defaultdict
from pathlib import Path

LOGS = Path.home() / "identity-prefix/logs"
VARIANTS = ("published", "prefix", "suffix", "spliced")

for lane in ("laguna", "qwen"):
    f = LOGS / f"identity_{lane}.jsonl"
    if not f.exists():
        continue
    rows = [json.loads(l) for l in f.read_text().splitlines()]
    ok = [r for r in rows if r.get("http_status") == 200]
    errs = [r for r in rows if r.get("http_status") != 200]
    cells = defaultdict(list)
    for r in ok:
        cells[(r["condition"], r["variant"])].append(r)
    bytask = defaultdict(list)
    for r in ok:
        bytask[(r["condition"], r["variant"], r["task_type"])].append(r)
    print(f"\n=== {lane} ({len(ok)} ok, {len(errs)} errors) ===")
    print(f"{'cell':22s} {'fired':>8s} {'rtok_med':>9s} {'ctok_med':>9s} "
          f"{'ptok_med':>9s} {'len_fr':>7s} {'shim':>5s}")
    for cond in ("C6", "C7"):
        for v in VARIANTS:
            rs = cells.get((cond, v), [])
            if not rs:
                print(f"{cond}/{v:18s} (no data)")
                continue
            fired = sum(1 for r in rs if r["thinking_fired"])
            rtoks = sorted(r["thinking_tokens_est"] for r in rs
                           if r["thinking_fired"]) or [0]
            ctoks = sorted(r.get("completion_tokens") or 0 for r in rs)
            ptoks = sorted(r.get("prompt_tokens") or 0 for r in rs)
            lens = sum(1 for r in rs if r.get("finish_reason") == "length")
            shim = sum(1 for r in rs if r.get("shim_hit"))
            print(f"{cond}/{v:18s} {fired:>3d}/{len(rs):<3d} "
                  f"{rtoks[len(rtoks)//2]:>9d} {ctoks[len(ctoks)//2]:>9d} "
                  f"{ptoks[len(ptoks)//2]:>9d} {lens:>7d} {shim:>5d}")
    print("  per-task fired:")
    for cond in ("C6", "C7"):
        for v in VARIANTS:
            parts = []
            for t in ("math", "code", "reasoning", "summary"):
                rs = bytask.get((cond, v, t), [])
                fired = sum(1 for r in rs if r["thinking_fired"])
                parts.append(f"{t}={fired}/{len(rs)}")
            print(f"    {cond}/{v:12s} " + " ".join(parts))
    if errs:
        print("  ERRORS:")
        for r in errs[:10]:
            print("   ", r.get("condition"), r.get("variant"),
                  r.get("task_type"), r.get("sample"), r.get("error"))
