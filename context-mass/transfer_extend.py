#!/usr/bin/env python3
"""Extend Study A transfer check to n=40 (gate-study per-condition n).
The first 20 scored 9/20 (45%) — 5 pts under the band floor, within binomial
noise of 60% at n=20. This adds 20 more C7 samples (5 per task) + writes a
combined verdict. Decision rule for the extension: combined n=40 rate >= 0.50
-> proceed (in band); 0.40-0.50 -> borderline, proceed with scoping caveat
ONLY if reasoning-task firing >= 3/10 combined; < 0.40 -> divergence confirmed.
"""
import importlib.util, json, secrets, sys, os, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ORIG = "<UPSTREAM_DRIVER>/qwen_gate_study_driver.py"
spec = importlib.util.spec_from_file_location("qwen_base", ORIG)
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

sys.path.insert(0, os.path.expanduser("results/context_mass_sweep_20260729"))
import context_mass_sweep_driver as d

OUT = Path(os.path.expanduser("results/context_mass_sweep_20260729"))
tc = d.LOGS / "transfer_check.jsonl"

jobs = [(t, i, p) for t, p in base.TASKS.items() for i in range(5, 10)]

def one(j):
    t, i, p = j
    nonce = secrets.token_hex(4)
    status, resp, lat = d.chat(
        [{"role": "system", "content": base.C7},
         {"role": "user", "content": f"[run-{nonce}] {p}"}],
        d.PROBE_CEILING, thinking=True)
    row = {"phase": "transfer_check_ext", "condition": "C7", "task_type": t,
           "sample": i, "http_status": status, "latency_s": round(lat, 3)}
    if status == 200:
        m = d.measure(resp); m.pop("_content"); row.update(m)
    d.log(tc, row)
    print(f"ext {t} s{i} fired={row.get('thinking_fired')}", flush=True)
    return row

with ThreadPoolExecutor(max_workers=4) as ex:
    rows = list(ex.map(one, jobs))

# combined verdict over all 40
allrows = [json.loads(l) for l in tc.read_text().splitlines()]
ok = [r for r in allrows if r.get("http_status") == 200]
fired = sum(1 for r in ok if r.get("thinking_fired"))
rate = fired / len(ok)
per_task = {t: [sum(1 for r in ok if r.get("task_type") == t and r.get("thinking_fired")),
                sum(1 for r in ok if r.get("task_type") == t)] for t in base.TASKS}
reasoning_ok = per_task["reasoning"][0] >= 3
if rate >= 0.50:
    decision = "PROCEED_IN_BAND"
elif rate >= 0.40 and reasoning_ok:
    decision = "PROCEED_BORDERLINE_WITH_CAVEAT"
else:
    decision = "DIVERGENCE_CONFIRMED_STOP"
verdict = {"fired": fired, "total": len(ok), "rate": round(rate, 3),
           "per_task": per_task, "decision": decision,
           "note": "extension to n=40 after 9/20 first pass; rule in transfer_extend.py docstring"}
(OUT / "transfer_verdict_n40.json").write_text(json.dumps(verdict, indent=1))
print(json.dumps(verdict, indent=1))
