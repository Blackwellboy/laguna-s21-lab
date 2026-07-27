#!/usr/bin/env python3
"""Qwen 3.6 35B-A3B empty-at-ceiling map — 2026-07-29 (fable).

FOLLOW-UP to the 2026-07-28 cross-model gate study, which found the criteria
task returning empty content 28/30 at the 4096 ceiling across all conditions.

REUSED BYTE-IDENTICAL (imported from the original driver module, not copied):
  - CRITERIA_TASK (the exact criteria task text)
  - sampling (Qwen generation_config defaults: temp 1.0 / top_p 0.95 / top_k 20)
  - nonce-prefix scheme, enable_thinking:true, `message.reasoning` detection

ADAPTATIONS (documented):
  1. Budget axis: bare prompt (C0, no system prompt), max_tokens ceiling
     swept {4096, 8192, 12288, 16384}, 10 samples each.
  2. Shape axis: at the 12288 ceiling, 4 NEW structured task shapes (below),
     10 samples each. These four prompts are new text written for this study.
  3. Per-sample degeneration check on every cap-hit: unique-line ratio and
     zlib compression ratio over the reasoning tail (last 8000 chars) —
     the compression-ratio approach from the PR #10 discussion.
  4. request timeout raised 900 -> 1800 s (16384-token generations).
  5. Full reasoning text is NOT logged raw; we log length, tail metrics, and
     a 400-char tail preview per sample (enough to hand-verify degeneration).
"""
import importlib.util, json, os, secrets, sys, time, urllib.request, zlib
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

ORIG = "<UPSTREAM_DRIVER>/qwen_gate_study_driver.py"
spec = importlib.util.spec_from_file_location("qwen_base", ORIG)
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

CRITERIA_TASK = base.CRITERIA_TASK
TEMPERATURE, TOP_P, TOP_K = base.TEMPERATURE, base.TOP_P, base.TOP_K

ENDPOINT = "http://localhost:8100/v1"
MODEL = "nvidia/Qwen3.6-35B-A3B-NVFP4"
OUT = Path(os.path.expanduser("results/qwen_ceiling_map_20260729"))
LOGS = OUT / "logs"
LOGS.mkdir(parents=True, exist_ok=True)
CONC = int(os.environ.get("CONC", "4"))
_loglock = Lock()

CEILINGS = [4096, 8192, 12288, 16384]
SHAPE_CEILING = 12288
N = 10

# ---- shape-axis tasks (NEW text for this study) ----
SHAPES = {
    "numbered_requirements": (
        "Implement a Python function merge_intervals(intervals) for a "
        "scheduling system.\n\nRequirements:\n"
        "1. must accept a list of (start, end) integer tuples\n"
        "2. must merge all overlapping or adjacent intervals\n"
        "3. must return the merged list sorted by start\n"
        "4. must raise ValueError on any interval where end < start\n"
        "5. must not mutate the input list\n"
        "6. must handle an empty input list by returning []\n"
        "All six numbered requirements must be verifiably met; include a "
        "short test block demonstrating each."
    ),
    "json_schema_output": (
        "Produce ONLY a JSON object (no markdown fences, no prose) describing "
        "a deployment plan for a web service, valid against this schema: "
        "top-level keys 'service' (string), 'stages' (array of exactly 3 "
        "objects each with 'name' (string), 'steps' (array of 2-4 strings), "
        "'rollback' (string)), and 'health_check' (object with 'endpoint' "
        "(string) and 'timeout_s' (integer)). Every key is required."
    ),
    "table_construction": (
        "Construct a markdown table comparing four sorting algorithms "
        "(quicksort, mergesort, heapsort, insertion sort) with columns: "
        "Algorithm, Best case, Average case, Worst case, Space, Stable "
        "(yes/no), When to prefer. Fill every cell accurately; the "
        "'When to prefer' column must be a concrete one-sentence scenario. "
        "Output the table and nothing else."
    ),
    "multistep_math_constrained": (
        "A factory runs three production lines. Line A produces 240 units/day "
        "and each unit uses 1.5 kg of material. Line B produces 25 percent "
        "more units than A but each unit uses 20 percent less material. "
        "Line C produces half as many units as A and B combined, each using "
        "2 kg. Constraints: material stock is 1400 kg/day; any shortfall "
        "shuts down line C first, then B. Determine how many units each line "
        "actually produces on a day with full staffing, showing each step "
        "and stating which constraint binds. End with the three final numbers."
    ),
}


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def log(path, obj):
    obj = dict(obj); obj.setdefault("ts", utcnow())
    with _loglock:
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def note(msg):
    print(f"[{utcnow()}] {msg}", flush=True)


def chat(messages, max_tokens):
    body = {
        "model": MODEL, "messages": messages, "max_tokens": max_tokens,
        "temperature": TEMPERATURE, "top_p": TOP_P, "top_k": TOP_K,
        "chat_template_kwargs": {"enable_thinking": True},
    }
    req = urllib.request.Request(
        f"{ENDPOINT}/chat/completions", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=1800) as r:
            return r.status, json.load(r), time.time() - t0
    except Exception as e:
        return None, {"error": str(e)[:300]}, time.time() - t0


def degeneration_metrics(reasoning_tail):
    """Unique-line ratio + zlib compression ratio over the reasoning tail."""
    lines = [l for l in reasoning_tail.splitlines() if l.strip()]
    uniq = len(set(lines)) / len(lines) if lines else None
    data = reasoning_tail.encode("utf-8", errors="replace")
    comp = len(zlib.compress(data, 9)) / len(data) if data else None
    return {
        "tail_lines": len(lines),
        "tail_unique_line_ratio": round(uniq, 4) if uniq is not None else None,
        "tail_zlib_ratio": round(comp, 4) if comp is not None else None,
    }


def answer_checks(shape, content):
    """Shape-specific extractability check alongside plain non-emptiness."""
    c = content.strip()
    if not c:
        return {"answer_nonempty": False, "answer_shape_valid": False}
    valid = None
    if shape in ("criteria", "numbered_requirements"):
        valid = "def " in c
    elif shape == "json_schema_output":
        s = c[c.find("{"): c.rfind("}") + 1]
        try:
            j = json.loads(s)
            valid = all(k in j for k in ("service", "stages", "health_check"))
        except Exception:
            valid = False
    elif shape == "table_construction":
        valid = c.count("|") >= 20
    elif shape == "multistep_math_constrained":
        valid = any(ch.isdigit() for ch in c)
    return {"answer_nonempty": True, "answer_shape_valid": valid}


def run_sample(logfile, axis, shape, prompt, ceiling, idx):
    nonce = secrets.token_hex(4)
    messages = [{"role": "user", "content": f"[run-{nonce}] {prompt}"}]
    status, resp, lat = chat(messages, ceiling)
    row = {"axis": axis, "shape": shape, "ceiling": ceiling, "sample": idx,
           "nonce": nonce, "http_status": status, "latency_s": round(lat, 3),
           "concurrency": CONC}
    if status == 200:
        ch = (resp.get("choices") or [{}])[0]
        msg = ch.get("message") or {}
        content = msg.get("content") or ""
        rc = msg.get("reasoning_content") or msg.get("reasoning") or ""
        usage = resp.get("usage") or {}
        fr = ch.get("finish_reason")
        cap_hit = fr == "length"
        row.update({
            "thinking_fired": bool(rc),
            "reasoning_chars": len(rc),
            "reasoning_tokens_est": max(1, len(rc) // 4) if rc else 0,
            "content_chars": len(content),
            "completion_tokens": usage.get("completion_tokens"),
            "prompt_tokens": usage.get("prompt_tokens"),
            "finish_reason": fr,
            "cap_hit": cap_hit,
            "content_preview": content[:300],
        })
        row.update(answer_checks(shape, content))
        if cap_hit and rc:
            tail = rc[-8000:]
            row.update(degeneration_metrics(tail))
            row["reasoning_tail_preview"] = tail[-400:]
    else:
        row["error"] = resp.get("error", f"http_{status}")
    log(logfile, row)
    note(f"{axis} {shape} c{ceiling} s{idx}: fired={row.get('thinking_fired')} "
         f"cap={row.get('cap_hit')} nonempty={row.get('answer_nonempty')} "
         f"ctok={row.get('completion_tokens')} lat={row.get('latency_s')}")
    return row


def main():
    note(f"qwen ceiling map start endpoint={ENDPOINT} conc={CONC}")
    note(f"sampling temp={TEMPERATURE} top_p={TOP_P} top_k={TOP_K} (inherited from base driver)")
    lf = LOGS / "budget_axis.jsonl"
    for ceiling in CEILINGS:
        t0 = time.time()
        with ThreadPoolExecutor(max_workers=CONC) as ex:
            rows = list(ex.map(
                lambda i: run_sample(lf, "budget", "criteria", CRITERIA_TASK, ceiling, i),
                range(N)))
        ok = [r for r in rows if r.get("http_status") == 200]
        note(f"BUDGET ceiling={ceiling}: nonempty "
             f"{sum(1 for r in ok if r.get('answer_nonempty'))}/{len(ok)}, cap-hits "
             f"{sum(1 for r in ok if r.get('cap_hit'))}, {round(time.time()-t0)}s")
    lf2 = LOGS / "shape_axis.jsonl"
    for shape, prompt in SHAPES.items():
        t0 = time.time()
        with ThreadPoolExecutor(max_workers=CONC) as ex:
            rows = list(ex.map(
                lambda i: run_sample(lf2, "shape", shape, prompt, SHAPE_CEILING, i),
                range(N)))
        ok = [r for r in rows if r.get("http_status") == 200]
        note(f"SHAPE {shape}: nonempty "
             f"{sum(1 for r in ok if r.get('answer_nonempty'))}/{len(ok)}, cap-hits "
             f"{sum(1 for r in ok if r.get('cap_hit'))}, {round(time.time()-t0)}s")
    note("qwen ceiling map COMPLETE")


if __name__ == "__main__":
    main()
