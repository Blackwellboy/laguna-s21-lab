#!/usr/bin/env python3
"""Analysis for c7_depth_collapse_20260727. Pre-stated plan (see driver
docstring): primary = median thinking_tokens_est among FIRED per arm with
n-fired stated; secondary = firing rates; question of record = additive
stacking vs floor for identity+tools."""
import json, statistics, sys
from itertools import combinations
from pathlib import Path

LOG = Path.home() / "c7-depth-collapse/logs/depth_c7.jsonl"
ARMS = ("c7_bare", "c7_identity", "c7_neutral", "c7_tools", "c7_identity_tools")
TASKS = ("math", "code", "reasoning", "summary")

rows = [json.loads(l) for l in LOG.read_text().splitlines() if l.strip()]
ok = [r for r in rows if r.get("http_status") == 200]
# dedupe: keep first occurrence per (arm, task, sample)
seen, uniq = set(), []
for r in ok:
    k = (r["arm"], r["task_type"], r["sample"])
    if k not in seen:
        seen.add(k)
        uniq.append(r)

print(f"rows={len(rows)} ok={len(ok)} unique={len(uniq)} "
      f"errors={len(rows) - len(ok)} dupes_dropped={len(ok) - len(uniq)}")

def fisher(a, b, c, d):
    """two-sided Fisher exact on [[a,b],[c,d]]"""
    from math import comb
    n = a + b + c + d
    row1, col1 = a + b, a + c
    def p_of(x):
        return comb(row1, x) * comb(n - row1, col1 - x) / comb(n, col1)
    p_obs = p_of(a)
    lo = max(0, col1 - (n - row1)); hi = min(row1, col1)
    return sum(p_of(x) for x in range(lo, hi + 1) if p_of(x) <= p_obs * (1 + 1e-9))

def mannwhitney(x, y):
    """two-sided Mann-Whitney U, normal approx with tie correction"""
    import math
    nx, ny = len(x), len(y)
    if nx == 0 or ny == 0:
        return None
    allv = sorted((v, i) for i, v in enumerate(x + y))
    ranks = [0.0] * (nx + ny)
    i = 0
    while i < len(allv):
        j = i
        while j < len(allv) and allv[j][0] == allv[i][0]:
            j += 1
        r = (i + j + 1) / 2.0
        for k in range(i, j):
            ranks[allv[k][1]] = r
        i = j
    rx = sum(ranks[:nx])
    u = rx - nx * (nx + 1) / 2.0
    mu = nx * ny / 2.0
    # tie correction
    from collections import Counter
    cnt = Counter(v for v, _ in allv)
    n = nx + ny
    tie = sum(c**3 - c for c in cnt.values())
    var = nx * ny / 12.0 * ((n + 1) - tie / (n * (n - 1)))
    if var <= 0:
        return 1.0
    z = (u - mu) / math.sqrt(var)
    p = math.erfc(abs(z) / math.sqrt(2))
    return p

stats = {}
print("\n=== PRIMARY: depth among fired (thinking_tokens_est) ===")
print(f"{'arm':20s} {'n':>3s} {'fired':>5s} {'median':>7s} {'IQR':>13s} {'mean':>7s} {'ceil':>4s}")
for arm in ARMS:
    rs = [r for r in uniq if r["arm"] == arm]
    fired = [r for r in rs if r.get("thinking_fired")]
    depths = sorted(r["thinking_tokens_est"] for r in fired)
    ceil = sum(1 for r in fired if r.get("finish_reason") == "length")
    if depths:
        med = statistics.median(depths)
        q1 = depths[len(depths)//4]; q3 = depths[(3*len(depths))//4 - (1 if len(depths)>=4 else 0)]
        mean = statistics.mean(depths)
        print(f"{arm:20s} {len(rs):3d} {len(fired):5d} {med:7.0f} [{q1:5.0f},{q3:5.0f}] {mean:7.0f} {ceil:4d}")
    else:
        print(f"{arm:20s} {len(rs):3d} {len(fired):5d}     n/a")
    stats[arm] = {"n": len(rs), "n_fired": len(fired), "depths": depths,
                  "fired_ceiling": ceil,
                  "median_depth": statistics.median(depths) if depths else None}

print("\n=== per-task depth medians among fired (n_fired) ===")
hdr = f"{'arm':20s}" + "".join(f"{t:>16s}" for t in TASKS)
print(hdr)
for arm in ARMS:
    line = f"{arm:20s}"
    for t in TASKS:
        d = sorted(r["thinking_tokens_est"] for r in uniq
                   if r["arm"] == arm and r["task_type"] == t and r.get("thinking_fired"))
        line += f"{(str(round(statistics.median(d))) + ' (' + str(len(d)) + ')') if d else '- (0)':>16s}"
    print(line)

print("\n=== SECONDARY: firing rates ===")
for arm in ARMS:
    s = stats[arm]
    print(f"{arm:20s} {s['n_fired']}/{s['n']}")

print("\n=== pairwise Mann-Whitney on depth among fired (two-sided) ===")
for a, b in combinations(ARMS, 2):
    da, db = stats[a]["depths"], stats[b]["depths"]
    p = mannwhitney(da, db)
    if p is not None:
        print(f"{a:20s} vs {b:20s} n=({len(da)},{len(db)}) p={p:.4g}")

print("\n=== pairwise Fisher on firing ===")
for a, b in combinations(ARMS, 2):
    sa, sb = stats[a], stats[b]
    p = fisher(sa["n_fired"], sa["n"] - sa["n_fired"], sb["n_fired"], sb["n"] - sb["n_fired"])
    print(f"{a:20s} vs {b:20s} {sa['n_fired']}/{sa['n']} vs {sb['n_fired']}/{sb['n']} p={p:.4g}")

print("\n=== integrity ===")
shims = sum(1 for r in uniq if r.get("shim_hit"))
toolcalls = {arm: sum(r.get("n_tool_calls") or 0 for r in uniq if r["arm"] == arm) for arm in ARMS}
frs = {}
for r in uniq:
    frs[r.get("finish_reason")] = frs.get(r.get("finish_reason"), 0) + 1
print(f"shim_hits={shims} finish_reasons={frs} tool_calls_by_arm={toolcalls}")
lat = sorted(r["latency_s"] for r in uniq)
print(f"latency median={lat[len(lat)//2]:.1f}s max={lat[-1]:.1f}s")

out = {arm: {k: v for k, v in s.items() if k != "depths"} for arm, s in stats.items()}
summary_path = LOG.parent.parent / "summary.json"
summary_path.write_text(json.dumps(out, indent=2))
print(f"\nwrote {summary_path}")
