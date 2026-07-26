#!/usr/bin/env python3
"""Run the canonical 16-task intel suite (full_triple_maxspeed_20260723/full_harness.py,
prompts + grading UNTOUCHED) against ONE lane, N runs per task.

Env: LANE_BASE, LANE_MODEL, LANE_LABEL, LANE_FAMILY (payload branch), LANE_CTK (JSON
chat_template_kwargs override, optional), INTEL_RUNS (default 3), INTEL_OUT.
"""
import importlib.util, json, os, sys, time
from pathlib import Path

HARNESS = "<CONTROL_PLANE>/full_triple_maxspeed_20260723/full_harness.py"
spec = importlib.util.spec_from_file_location("fh", HARNESS)
fh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fh)

lane = "target"
fh.LANES = {lane: {
    "label": os.environ.get("LANE_LABEL", "target"),
    "base": os.environ["LANE_BASE"],
    "model": os.environ["LANE_MODEL"],
    "family": os.environ.get("LANE_FAMILY", "generic"),
    "hw": os.environ.get("LANE_HW", "1xGB10"),
}}

ctk = os.environ.get("LANE_CTK")
if ctk:
    ctk = json.loads(ctk)
    orig_payload = fh.payload
    def payload(l, messages, **kw):
        body = orig_payload(l, messages, **kw)
        body["chat_template_kwargs"] = ctk
        return body
    fh.payload = payload

mt_override = os.environ.get("INTEL_MT_OVERRIDE")
if mt_override:
    mt_override = int(mt_override)
    def intel_one(l, task):
        temp = 0.0 if task["cat"] in ("math", "reasoning", "structured") else 0.3
        body = fh.payload(l, [{"role": "user", "content": task["prompt"]}],
                          max_tokens=mt_override, temperature=temp, stream=False,
                          top_p=0.95 if temp > 0 else 1.0)
        code, resp, dt = fh.http_json("POST", f"{fh.LANES[l]['base']}/chat/completions", body, timeout=600)
        text = fh.extract_text(resp) if code == 200 else ""
        ok, detail = fh.grade(text, task["expect"]) if code == 200 else (False, f"http_{code}")
        return {"lane": l, "task_id": task["id"], "cat": task["cat"], "pass": ok, "detail": detail,
                "latency_s": round(dt, 4), "phase": fh.PHASE,
                "completion_tokens": (resp.get("usage") or {}).get("completion_tokens") if isinstance(resp, dict) else None,
                "preview": (text or "")[:400],
                "error": resp.get("error") if isinstance(resp, dict) else None}
    fh.intel_one = intel_one

runs = int(os.environ.get("INTEL_RUNS", "3"))
out_path = Path(os.environ.get("INTEL_OUT", "intel16_results.json"))

if not fh.wait_ok(lane, timeout=60):
    print("LANE NOT READY", file=sys.stderr); sys.exit(2)

all_rows = []
for r in range(runs):
    for task in fh.INTEL:
        row = fh.intel_one(lane, task)
        row["run"] = r
        all_rows.append(row)
        print(f"run{r} {task['id']:14s} pass={row['pass']} {row['detail']}", flush=True)

# per-task majority + per-run totals
per_task = {}
for row in all_rows:
    per_task.setdefault(row["task_id"], []).append(row["pass"])
majority = {k: (sum(v) > len(v)/2) for k, v in per_task.items()}
per_run = [sum(1 for x in all_rows if x["run"] == r and x["pass"]) for r in range(runs)]
summary = {
    "label": fh.LANES[lane]["label"], "model": fh.LANES[lane]["model"],
    "base": fh.LANES[lane]["base"], "runs": runs,
    "per_run_score": per_run, "n_tasks": len(fh.INTEL),
    "majority_score": sum(majority.values()),
    "majority_by_task": majority,
    "chat_template_kwargs": ctk,
    "rows": all_rows,
}
out_path.write_text(json.dumps(summary, indent=2))
print(json.dumps({k: summary[k] for k in ("label","per_run_score","majority_score","n_tasks")}))
