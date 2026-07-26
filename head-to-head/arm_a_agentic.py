#!/usr/bin/env python3
"""Arm A — agentic/multi-turn shape. 3 scenarios x 3 runs, native tool-calling.

Scenario = multi-turn loop: model gets tools, must (1) call the right tool with valid
JSON args, (2) incorporate the tool result on the next turn, (3) finish with a correct
final answer. Scored on: valid tool_call turn-1, correct tool choice, args parse,
final-answer correctness. Also records decode speed on the final synthesis turn.

Env: LANE_BASE, LANE_MODEL, LANE_LABEL, LANE_CTK (JSON, optional), ARM_RUNS (3),
ARM_OUT, LANE_SAMPLING (JSON dict merged into request, e.g. model-default temps).
"""
import json, os, time, urllib.request
from pathlib import Path

BASE = os.environ["LANE_BASE"]; MODEL = os.environ["LANE_MODEL"]
CTK = json.loads(os.environ["LANE_CTK"]) if os.environ.get("LANE_CTK") else None
SAMP = json.loads(os.environ.get("LANE_SAMPLING", "{}"))
RUNS = int(os.environ.get("ARM_RUNS", "3"))
OUT = Path(os.environ.get("ARM_OUT", "arm_a_results.json"))

def chat(messages, tools=None, max_tokens=700):
    body = {"model": MODEL, "messages": messages, "max_tokens": max_tokens, **SAMP}
    if tools: body["tools"] = tools; body["tool_choice"] = "auto"
    if CTK: body["chat_template_kwargs"] = CTK
    req = urllib.request.Request(f"{BASE}/chat/completions", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": "Bearer dummy"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=600) as r:
        resp = json.loads(r.read().decode())
    return resp, time.perf_counter() - t0

TOOLS = [
    {"type":"function","function":{"name":"read_file","description":"Read a file","parameters":{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}}},
    {"type":"function","function":{"name":"run_tests","description":"Run test command","parameters":{"type":"object","properties":{"cmd":{"type":"string"}},"required":["cmd"]}}},
    {"type":"function","function":{"name":"http_get","description":"GET a URL","parameters":{"type":"object","properties":{"url":{"type":"string"}},"required":["url"]}}},
    {"type":"function","function":{"name":"calc","description":"Evaluate arithmetic expression","parameters":{"type":"object","properties":{"expr":{"type":"string"}},"required":["expr"]}}},
]

SCENARIOS = [
    {
        "id": "debug_loop",
        "expect_tool": "read_file",
        "user": "The test test_parse_config fails with KeyError: 'timeout'. The config loader is in src/config.py. Investigate and fix. Start by reading the relevant file.",
        "tool_result": "def load(path):\n    raw = json.load(open(path))\n    return {'host': raw['host'], 'port': raw['port'], 'timeout': raw['timeout']}\n",
        "followup": "Now state the minimal fix as a single line of replacement code for the return statement, defaulting timeout to 30.",
        "final_check": lambda t: ("raw.get('timeout', 30)" in t.replace('\"',"'")) or ("get('timeout'" in t.replace('\"',"'") and "30" in t),
    },
    {
        "id": "ops_probe",
        "expect_tool": "http_get",
        "user": "Check whether the service at http://10.0.0.5:8000/health is up, then summarize status. Use a tool first, do not guess.",
        "tool_result": "{\"status\": \"degraded\", \"kv_cache_pct\": 97, \"queue_depth\": 41}",
        "followup": "Given that result, give the single most likely cause and the one command-line flag you would tune first.",
        "final_check": lambda t: any(k in t.lower() for k in ["kv", "cache", "memory", "max-num-seqs", "gpu-memory-utilization", "queue"]),
    },
    {
        "id": "calc_chain",
        "expect_tool": "calc",
        "user": "A model decodes 34.0 tok/s with a drafter and 23.0 tok/s without. Use the calc tool to compute the percent speedup ((34-23)/23*100), do not compute it yourself.",
        "tool_result": "47.826086956521735",
        "followup": "Report the speedup as a percentage rounded to one decimal, number only with a % sign.",
        "final_check": lambda t: "47.8" in t,
    },
]

rows = []
for run in range(RUNS):
    for sc in SCENARIOS:
        rec = {"run": run, "id": sc["id"], "tool_called": False, "right_tool": False,
               "args_valid": False, "final_ok": False, "error": None}
        try:
            msgs = [{"role":"user","content":sc["user"]}]
            resp, _ = chat(msgs, tools=TOOLS)
            msg = resp["choices"][0]["message"]
            tcs = msg.get("tool_calls") or []
            if tcs:
                rec["tool_called"] = True
                fn = tcs[0]["function"]
                rec["right_tool"] = fn["name"] == sc["expect_tool"]
                try:
                    json.loads(fn["arguments"]); rec["args_valid"] = True
                except Exception: pass
                msgs.append({"role":"assistant","content":msg.get("content") or "","tool_calls":tcs})
                msgs.append({"role":"tool","tool_call_id":tcs[0]["id"],"content":sc["tool_result"]})
                msgs.append({"role":"user","content":sc["followup"]})
                resp2, dt2 = chat(msgs, tools=TOOLS)
                m2 = resp2["choices"][0]["message"]
                final = (m2.get("content") or "").strip()
                if not final and m2.get("tool_calls"):
                    # model chained another tool call; give it the same result and ask again
                    msgs.append({"role":"assistant","content":"","tool_calls":m2["tool_calls"]})
                    msgs.append({"role":"tool","tool_call_id":m2["tool_calls"][0]["id"],"content":sc["tool_result"]})
                    resp3, _ = chat(msgs)
                    final = (resp3["choices"][0]["message"].get("content") or "").strip()
                rec["final_ok"] = bool(sc["final_check"](final))
                rec["final_preview"] = final[:200]
                rec["final_latency_s"] = round(dt2, 2)
                u = resp2.get("usage") or {}
                rec["final_completion_tokens"] = u.get("completion_tokens")
        except Exception as e:
            rec["error"] = str(e)[:300]
        rec["score"] = sum([rec["tool_called"], rec["right_tool"], rec["args_valid"], rec["final_ok"]])
        rows.append(rec)
        print(f"run{run} {sc['id']:12s} score={rec['score']}/4 final_ok={rec['final_ok']} err={rec['error']}", flush=True)

total = sum(r["score"] for r in rows); maxs = 4 * len(rows)
summary = {"label": os.environ.get("LANE_LABEL"), "model": MODEL, "sampling": SAMP,
           "ctk": CTK, "runs": RUNS, "total": total, "max": maxs,
           "pct": round(100*total/maxs, 1), "rows": rows}
OUT.write_text(json.dumps(summary, indent=2))
print(json.dumps({k: summary[k] for k in ("label","total","max","pct")}))
