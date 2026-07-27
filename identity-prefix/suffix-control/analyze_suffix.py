#!/usr/bin/env python3
"""Analysis for the identity-suffix control experiment (2026-07-27).

Dedupe rule: an orphan second driver briefly ran on the laguna lane
(08:27:22Z to 08:29:35Z) before being killed; for any duplicated
(variant, task, sample) cell the LAST row (surviving driver) is kept and the
orphan row dropped. All laguna rows whose timestamp falls inside the dual
window are re-flagged latency_polluted regardless of which driver wrote them.
Firing is prompt-determined and unaffected (standing rationale, 2026-07-28).
"""
import json, sys
from collections import Counter, defaultdict
from math import comb
from pathlib import Path

LOGS = Path(__file__).parent / "logs"
VARIANTS = ("none", "suffix_identity", "suffix_neutral", "suffix_topical")
TASKS = ("math", "code", "reasoning", "summary")
DUAL_WINDOW = ("2026-07-27T08:25:55", "2026-07-27T08:29:35")


def fisher_two_sided(a, b, c, d):
    """2x2 exact test: [[a, b], [c, d]] rows = groups, cols = fired/not."""
    n = a + b + c + d
    r1, c1 = a + b, a + c
    def p_table(x):
        return comb(c1, x) * comb(n - c1, r1 - x) / comb(n, r1)
    p_obs = p_table(a)
    lo, hi = max(0, r1 - (n - c1)), min(r1, c1)
    return sum(p_table(x) for x in range(lo, hi + 1)
               if p_table(x) <= p_obs * (1 + 1e-9))


def load(lane):
    rows = [json.loads(l) for l in
            (LOGS / f"suffix_{lane}.jsonl").read_text().splitlines()]
    rows = [r for r in rows if r.get("http_status") == 200]
    byc = {}
    dropped = []
    for r in rows:  # file order; later overwrite = keep last
        k = (r["variant"], r["task_type"], r["sample"])
        if k in byc:
            dropped.append(byc[k])
        byc[k] = r
    out = list(byc.values())
    if lane == "laguna":
        for r in out:
            if DUAL_WINDOW[0] <= r["ts"][:19] <= DUAL_WINDOW[1]:
                r["latency_polluted"] = True
    return out, dropped


def median(xs):
    xs = sorted(xs)
    if not xs:
        return None
    m = len(xs) // 2
    return xs[m] if len(xs) % 2 else (xs[m - 1] + xs[m]) / 2


def main():
    for lane in ("laguna", "qwen"):
        rows, dropped = load(lane)
        print(f"\n===== {lane.upper()} n={len(rows)} "
              f"(dropped {len(dropped)} orphan-driver duplicates) =====")
        errors = sum(1 for r in rows if r.get("http_status") != 200)
        polluted = sum(1 for r in rows if r.get("latency_polluted"))
        print(f"errors={errors} latency_polluted_rows={polluted}")

        # cell table
        fired = defaultdict(int)
        per_task = defaultdict(lambda: defaultdict(int))
        depth = defaultdict(list)
        for r in rows:
            v = r["variant"]
            if r["thinking_fired"]:
                fired[v] += 1
                per_task[v][r["task_type"]] += 1
                depth[v].append(r["thinking_tokens_est"])
        print(f"\n{'variant':<17} {'fired':>7} " +
              " ".join(f"{t:>9}" for t in TASKS) +
              "   depth_med  depth_mean")
        for v in VARIANTS:
            n = sum(1 for r in rows if r["variant"] == v)
            d = depth[v]
            print(f"{v:<17} {fired[v]:>3}/{n:<3} " +
                  " ".join(f"{per_task[v][t]:>6}/10" for t in TASKS) +
                  f"   {median(d) if d else '-':>9} "
                  f"{round(sum(d)/len(d)) if d else '-':>10}")

        # pairwise Fisher (pooled 40s)
        print("\nFisher exact (two-sided), pooled per variant:")
        pairs = [("suffix_identity", "none"), ("suffix_neutral", "none"),
                 ("suffix_topical", "none"),
                 ("suffix_identity", "suffix_neutral"),
                 ("suffix_identity", "suffix_topical"),
                 ("suffix_neutral", "suffix_topical")]
        for va, vb in pairs:
            na = sum(1 for r in rows if r["variant"] == va)
            nb = sum(1 for r in rows if r["variant"] == vb)
            a, c = fired[va], fired[vb]
            p = fisher_two_sided(a, na - a, c, nb - c)
            print(f"  {va} {a}/{na} vs {vb} {c}/{nb}: p={p:.4g}")

        # interleave proof
        seq = [r for r in sorted(rows, key=lambda r: r["ts"])]
        runs, best = 1, 1
        for i in range(1, len(seq)):
            if seq[i]["variant"] == seq[i - 1]["variant"]:
                runs += 1
                best = max(best, runs)
            else:
                runs = 1
        quartet_ok = all(
            {seq[k + j]["variant"] for j in range(4)} == set(VARIANTS)
            for k in range(0, len(seq) - 3, 4))
        print(f"\nInterleave proof: max same-variant run length in execution "
              f"order = {best}; every aligned quartet covers all 4 variants: "
              f"{quartet_ok}")
        print("First 12 in execution order:",
              [s["variant"].replace("suffix_", "") for s in seq[:12]])


if __name__ == "__main__":
    main()
