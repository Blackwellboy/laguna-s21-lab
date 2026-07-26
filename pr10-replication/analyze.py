#!/usr/bin/env python3
"""Aggregate PR#10 A/B results: pass@1 per arm (mean +/- spread over seeds),
flaky problems per arm, cap-hit / no-extractable-answer / degeneration analysis.
Run AFTER evalplus.evaluate produced eval_results.json for each samples file.
"""
import json, sys, glob, statistics
from pathlib import Path

outdir = Path(sys.argv[1])
rows = [json.loads(l) for l in (outdir / "raw_turns.jsonl").read_text().splitlines()]

# --- evalplus results ---
def load_eval(arm, seed):
    # evalplus writes <samples-stem>.eval_results.json (0.3.x: eval_results field "eval")
    cands = list(outdir.glob(f"samples_{arm}_s{seed}*eval_results.json"))
    assert cands, f"missing eval results for {arm} s{seed}"
    d = json.load(open(cands[0]))
    res = d["eval"]
    out = {}
    for tid, entries in res.items():
        e = entries[0]  # one sample per task
        base = e["base_status"] if "base_status" in e else e.get("base", [None])[0]
        plus = e["plus_status"] if "plus_status" in e else e.get("plus", [None])[0]
        out[tid] = {"base": base == "pass", "plus": plus == "pass"}
    return out

evals = {}
for arm in ("on", "off"):
    for s in (0, 1, 2):
        evals[(arm, s)] = load_eval(arm, s)

ids = sorted({r["task_id"] for r in rows}, key=lambda t: int(t.split("/")[1]))
print(f"n problems = {len(ids)}")

print("\n=== pass@1 (evalplus test execution; base = HumanEval, plus = HumanEval+) ===")
summary = {}
for arm in ("on", "off"):
    for metric in ("base", "plus"):
        vals = []
        for s in (0, 1, 2):
            ev = evals[(arm, s)]
            # a task missing from samples (error row) counts as fail
            passed = sum(1 for t in ids if ev.get(t, {}).get(metric))
            vals.append(100.0 * passed / len(ids))
        m = statistics.mean(vals)
        sd = statistics.stdev(vals)
        summary[(arm, metric)] = (m, sd, vals)
        print(f"  {arm:>3} {metric:<5} mean {m:6.2f}%  sd {sd:4.2f}  seeds {['%.2f' % v for v in vals]}")
for metric in ("base", "plus"):
    d = summary[("on", metric)][0] - summary[("off", metric)][0]
    print(f"  delta ON-OFF ({metric}): {d:+.2f} pts")

print("\n=== flaky problems per arm (pass in >=1 seed AND fail in >=1 seed, plus tests) ===")
for arm in ("on", "off"):
    flaky = []
    for t in ids:
        outcomes = {evals[(arm, s)].get(t, {}).get("plus", False) for s in (0, 1, 2)}
        if outcomes == {True, False}:
            flaky.append(t)
    print(f"  {arm:>3}: {len(flaky)} flaky  {flaky}")

print("\n=== per-arm telemetry ===")
for arm in ("on", "off"):
    rs = [r for r in rows if r["arm"] == arm and "error" not in r]
    errs = [r for r in rows if r["arm"] == arm and "error" in r]
    fired = sum(1 for r in rs if r["thinking_fired"])
    caps = [r for r in rs if r["cap_hit"]]
    noext = [r for r in rs if not r["extractable"]]
    ctoks = sorted(r["completion_tokens"] for r in rs)
    n = len(ctoks)
    p50 = ctoks[n // 2]; p95 = ctoks[int(n * 0.95)]
    print(f"  {arm:>3}: n={n} errors={len(errs)} fired={fired} cap_hits={len(caps)} "
          f"no_extract={len(noext)} ctok p50={p50} p95={p95} max={ctoks[-1]} "
          f"mean_wall={statistics.mean(r['seconds'] for r in rs):.1f}s")

print("\n=== cap-hit detail (degeneration check: tail compression ratio; loops compress hard) ===")
for arm in ("on", "off"):
    for r in rows:
        if r["arm"] == arm and r.get("cap_hit"):
            print(f"  {arm} {r['task_id']} s{r['seed']} ratio={r.get('tail_compression_ratio')} "
                  f"extract={r['extractable']} rtok~chars={r['reasoning_chars']} content_chars={r['content_chars']}")

print("\n=== no-extractable-answer detail ===")
for r in rows:
    if "error" not in r and not r["extractable"]:
        print(f"  {r['arm']} {r['task_id']} s{r['seed']} cap={r['cap_hit']} "
          f"finish={r['finish_reason']} content_chars={r['content_chars']} reasoning_chars={r['reasoning_chars']}")

print("\n=== control check: reasoning in OFF arm (must be ~0) ===")
bad = [r for r in rows if r["arm"] == "off" and "error" not in r and r["thinking_fired"]]
print(f"  OFF rows with thinking fired: {len(bad)}  {[ (r['task_id'], r['seed']) for r in bad ][:10]}")

on_fired = [r for r in rows if r["arm"] == "on" and "error" not in r and r["thinking_fired"]]
on_all = [r for r in rows if r["arm"] == "on" and "error" not in r]
print(f"  ON rows fired: {len(on_fired)}/{len(on_all)}")

# stray </think> artifact check
lead = sum(1 for r in rows if "error" not in r and r["content"].lstrip().startswith("</think>"))
print(f"\n  rows whose content starts with stray '</think>': {lead}")
