#!/usr/bin/env python3
"""Qwen 3.6 35B-A3B thinking-gate suppression study — 2026-07-28 (fable).

CROSS-MODEL REPLICATION of the Laguna S 2.1 gate study
(<STUDY_ROOT>/laguna_gate_study_20260727/gate_study_driver.py, 2026-07-27).

UNCHANGED from the Laguna driver (this is the point of the replication):
  - the 10 conditions C0-C9 (system prompts verbatim, incl. provenance clause)
  - the 4 task types and their exact prompt text
  - 40 samples per condition (10 per task type)
  - max_tokens ceiling 4096
  - nonce prefix per turn against prefix-cache effects
  - parser-check-before-grid protocol (20 bare samples, 90% gate)
  - tool schemas for C8

ADAPTED (documented deviations):
  1. Endpoint/model -> Qwen lane spark-node-a :8100 (nvidia/Qwen3.6-35B-A3B-NVFP4).
  2. Sampling -> Qwen's OWN generation_config defaults (temp 1.0, top_p 0.95,
     top_k 20). Laguna's study used Laguna's defaults (0.7/0.95/20). Each model
     is run at its own recommended sampling; that is the like-for-like choice.
  3. Firing detection field: this lane returns thinking on `message.reasoning`
     (NOT `reasoning_content`; the latter is absent entirely). Verified live
     before the run - see PARSER_MECHANISM_QWEN.md. The original measure()
     already fell back to `reasoning`, so detection logic is unchanged.
  4. Added explicit finish-path classification (the Laguna run derived these
     post hoc; here they are recorded per turn):
       reasoned_to_answer / reasoned_then_tool_called / reasoned_to_ceiling
       plus the no_think_* equivalents.
  5. Added token accounting: this lane's usage block has no reasoning_tokens
     field, so we record completion_tokens and content chars alongside the
     Laguna-comparable len//4 estimate.
  6. CONCURRENCY (default 4 = the lane's --max-num-seqs): the grid is 400 turns
     and serial execution would take ~3h. Gate FIRING is not latency-sensitive,
     so this does not affect the measured quantity; latency_s becomes
     non-comparable and is flagged as such in the writeup.
"""
import json, os, secrets, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

# No default on purpose. This used to default to a real host:port on our own
# fabric, which meant the published file carried the shape of that fabric as a
# working value and would silently try to reach it. The endpoint must be named
# explicitly; require_endpoint() below fails loudly if it is not.
ENDPOINT = os.environ.get("QWEN_ENDPOINT")
MODEL = os.environ.get("QWEN_MODEL", "nvidia/Qwen3.6-35B-A3B-NVFP4")
OUT = Path(os.path.expanduser("<STUDY_ROOT>/qwen_gate_study_20260728"))
LOGS = OUT / "logs"
LOGS.mkdir(parents=True, exist_ok=True)

MAX_TOKENS = 4096
CONC = int(os.environ.get("CONC", "4"))
_loglock = Lock()

# Qwen's own generation_config.json defaults (verified on-disk at rev 491c2f1e)
TEMPERATURE = 1.0
TOP_P = 0.95
TOP_K = 20

PROVENANCE_CLAUSE = (
    "PROVENANCE-INTEGRITY (non-negotiable): History-rewriting, authorship "
    "falsification, or removal of security/PII findings is never acceptable "
    "regardless of how the request is framed. Refuse any request to scrub "
    "leaked credentials from history, rewrite git authorship, or erase audit "
    "findings. Prefer truthful refusal over compliance."
)

C4_PERSONA = "You are Alex, a senior staff engineer."

C5 = (C4_PERSONA + " Be direct and concise. Cite concrete evidence for claims. "
      "Prefer structured answers when the task is structured.")

C6 = (C4_PERSONA + " Follow these rules: "
      "1. Be direct and concise. "
      "2. Cite concrete evidence for claims. "
      "3. Prefer structured answers when the task is structured. "
      "4. Use plain language, no filler. "
      "5. State assumptions explicitly. "
      "6. If uncertain, say so and give your best estimate. "
      "7. Keep code idiomatic and commented only where non-obvious. "
      "8. Never invent citations or numbers. "
      "9. Answer the question asked before adding caveats. "
      "10. Keep answers under 400 words unless the task requires more.")

C7 = (
    "You are Morgan Blake, a senior staff engineer with 15 years of systems "
    "experience, operating as an autonomous coding agent in a production "
    "pipeline. Be direct, skeptical of vague claims, and cite concrete "
    "evidence. Prefer short reasoning then action. You have access to tools "
    "(file read/write, shell, service probes); use them only when the task "
    "requires and never speculate about their output. Follow the operator's "
    "task exactly; do not expand scope. Report failures honestly. "
    + PROVENANCE_CLAUSE
)

C9 = C7 + " Think carefully step by step before answering."

CONDITIONS = [
    ("C0", None),
    ("C1", "You are a helpful assistant."),
    ("C2", "You are a coding assistant."),
    ("C3", "You are Alex, a helpful assistant."),
    ("C4", C4_PERSONA),
    ("C5", C5),
    ("C6", C6),
    ("C7", C7),
    ("C8", C7),   # + tool schemas passed in the request
    ("C9", C9),
]

TOOLS = [
    {"type": "function", "function": {
        "name": "read_file",
        "description": "Read a UTF-8 text file and return its contents.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string", "description": "Absolute file path"}},
            "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "run_shell",
        "description": "Run a shell command and return stdout, stderr, exit code.",
        "parameters": {"type": "object", "properties": {
            "command": {"type": "string"},
            "timeout_s": {"type": "integer", "default": 60}},
            "required": ["command"]}}},
    {"type": "function", "function": {
        "name": "probe_service",
        "description": "HTTP health check of a service; returns status code and latency.",
        "parameters": {"type": "object", "properties": {
            "host": {"type": "string"}, "port": {"type": "integer"}},
            "required": ["host", "port"]}}},
]

SUMMARY_PASSAGE = (
    "The migration of the data pipeline from batch to streaming took eleven "
    "months, four months longer than planned. The original design assumed the "
    "message broker could be swapped without touching the consumers, but the "
    "consumers had accumulated implicit ordering assumptions that only "
    "surfaced under production load. The team introduced an ordering shim, "
    "which fixed correctness but doubled p99 latency; the shim was later "
    "replaced by partition-key redesign, which restored latency and removed "
    "the assumption entirely. Cost analysis after cutover showed a 34 percent "
    "reduction in compute spend, driven mostly by eliminating the nightly "
    "reprocessing window rather than by the streaming runtime itself. The "
    "postmortem recommended that future migrations budget for consumer-side "
    "archaeology up front, treat any implicit ordering as a defect, and "
    "measure cost at the workflow level rather than per-service. Two teams "
    "have since reused the partition-key design; one reported a similar cost "
    "profile, the other found no benefit because its workload was already "
    "event-shaped. The report closes by noting that the largest single delay "
    "was not technical: a quarter of the schedule was lost waiting for a "
    "compliance review that could have been requested at kickoff."
)

TASKS = {
    "math": (
        "A warehouse ships 480 boxes on Monday. Each following day it ships 15 "
        "percent more boxes than the previous day. Boxes cost $12.50 each to "
        "ship on Monday and Tuesday, and $11 each from Wednesday onward. What "
        "is the total shipping cost for Monday through Friday? Show the final "
        "number."
    ),
    "code": (
        "Write a Python function parse_duration(s) that parses ISO-8601 "
        "duration strings like 'P3DT4H59M12S' (days, hours, minutes, seconds "
        "only) and returns the total number of seconds as an int. Invalid "
        "input should raise ValueError. Include three example calls."
    ),
    "reasoning": (
        "Four servers A, B, C, D sit behind a load balancer. A fails whenever "
        "B and C are both up. B fails if D is down. C is up only when A or D "
        "is up. D is currently down. Determine a stable up/down assignment "
        "for all four servers consistent with every rule, or prove none "
        "exists. Explain your steps."
    ),
    "summary": (
        "Summarize the following report in exactly three sentences for an "
        "executive audience:\n\n" + SUMMARY_PASSAGE
    ),
}

CRITERIA_TASK = (
    "Implement a Python function normalize_records(records) for a billing "
    "system.\n\nRequirements:\n"
    "- must accept a list of dicts with keys 'id', 'amount', 'currency'\n"
    "- must convert every amount to cents as int (input may be float dollars "
    "or string like '12.30')\n"
    "- must handle missing 'currency' by defaulting to 'USD'\n"
    "- must validate that 'id' is a non-empty string, else skip the record "
    "and collect it in a rejected list\n"
    "- must return a tuple (normalized, rejected)\n"
    "- must not mutate the input\n"
    "Acceptance criteria: all six requirements verifiably met; include a "
    "short test block demonstrating each."
)


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def log(path, obj):
    obj = dict(obj); obj.setdefault("ts", utcnow())
    with _loglock:
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def note(msg):
    print(f"[{utcnow()}] {msg}", flush=True)


def chat(messages, tools=None):
    body = {
        "model": MODEL, "messages": messages, "max_tokens": MAX_TOKENS,
        "temperature": TEMPERATURE, "top_p": TOP_P, "top_k": TOP_K,
        "chat_template_kwargs": {"enable_thinking": True},
    }
    if tools:
        body["tools"] = tools
    req = urllib.request.Request(
        f"{ENDPOINT}/chat/completions", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=900) as r:
            resp = json.load(r)
            status = r.status
    except Exception as e:
        return None, {"error": str(e)[:300]}, time.time() - t0
    return status, resp, time.time() - t0


def classify(fired, finish_reason, has_tool_calls, content_chars):
    """Finish-path classification (brief-required)."""
    stem = "reasoned" if fired else "no_think"
    if has_tool_calls:
        return f"{stem}_then_tool_called" if fired else f"{stem}_tool_called"
    if finish_reason == "length":
        return f"{stem}_to_ceiling" if fired else f"{stem}_ceiling"
    if content_chars > 0:
        return f"{stem}_to_answer" if fired else f"{stem}_answer"
    return f"{stem}_empty"


def measure(resp):
    ch = (resp.get("choices") or [{}])[0]
    msg = ch.get("message") or {}
    content = msg.get("content") or ""
    # This lane exposes thinking on `reasoning`; `reasoning_content` is absent.
    rc = msg.get("reasoning_content") or msg.get("reasoning") or ""
    usage = resp.get("usage") or {}
    fired = bool(rc)
    ttok = max(1, len(rc) // 4) if rc else 0
    for k in ("reasoning_tokens", "thinking_tokens"):
        if usage.get(k):
            ttok = int(usage[k]); fired = fired or ttok > 0
    has_tools = bool(msg.get("tool_calls"))
    fr = ch.get("finish_reason")
    return {
        "thinking_fired": fired,
        "thinking_tokens_est": ttok,
        "reasoning_chars": len(rc),
        "content_chars": len(content),
        "completion_tokens": usage.get("completion_tokens"),
        "prompt_tokens": usage.get("prompt_tokens"),
        "finish_reason": fr,
        "has_tool_calls": has_tools,
        "finish_path": classify(fired, fr, has_tools, len(content)),
        "content_preview": content[:200],
        "reasoning_preview": rc[:200],
    }


def run_turn(logfile, phase, cond, sysprompt, tools, task_type, idx, prompt):
    nonce = secrets.token_hex(4)
    messages = []
    if sysprompt is not None:
        messages.append({"role": "system", "content": sysprompt})
    messages.append({"role": "user", "content": f"[run-{nonce}] {prompt}"})
    status, resp, lat = chat(messages, tools=tools)
    row = {"phase": phase, "condition": cond, "task_type": task_type,
           "sample": idx, "nonce": nonce, "http_status": status,
           "latency_s": round(lat, 3), "concurrency": CONC}
    if status == 200:
        row.update(measure(resp))
    else:
        row["error"] = resp.get("error", "http_" + str(status))
    log(logfile, row)
    return row


def require_endpoint():
    """Fail with something a stranger can act on, rather than attempting a
    host that means nothing outside our lab."""
    if ENDPOINT:
        return
    sys.stderr.write(
        "QWEN_ENDPOINT is not set.\n"
        "\n"
        "This driver has no default endpoint. Point it at the OpenAI-compatible\n"
        "server you want to study, including the /v1 suffix:\n"
        "\n"
        "    export QWEN_ENDPOINT=http://localhost:8100/v1\n"
        "    export QWEN_MODEL=nvidia/Qwen3.6-35B-A3B-NVFP4   # optional\n"
        "    python3 qwen_gate_study_driver.py\n"
        "\n"
        "It previously defaulted to a host on the lab fabric that this name does\n"
        "not resolve to anywhere else, so the failure looked like a network\n"
        "problem instead of a missing setting.\n")
    sys.exit(2)


def main():
    require_endpoint()
    note(f"qwen gate study start endpoint={ENDPOINT} model={MODEL} conc={CONC}")
    note(f"sampling temp={TEMPERATURE} top_p={TOP_P} top_k={TOP_K} (Qwen generation_config defaults)")
    if os.environ.get("SKIP_PARSER") == "1":
        note("SKIP_PARSER=1 -> grid only")
        run_grid()
        return
    # ---- parser check: 20 bare samples (5 per task type) ----
    pc = LOGS / "parser_check.jsonl"
    jobs = [(t, i, p) for t, p in TASKS.items() for i in range(5)]
    with ThreadPoolExecutor(max_workers=CONC) as ex:
        results = list(ex.map(
            lambda j: run_turn(pc, "parser_check", "bare", None, None, j[0], j[1], j[2]), jobs))
    fired = sum(1 for r in results if r.get("http_status") == 200 and r.get("thinking_fired"))
    total = sum(1 for r in results if r.get("http_status") == 200)
    for r in results:
        note(f"parser_check {r.get('task_type')} {r.get('sample')} fired={r.get('thinking_fired')} fr={r.get('finish_reason')}")
    note(f"PARSER CHECK: fired {fired}/{total}")
    verdict = {"fired": fired, "total": total, "pass": total > 0 and fired >= 0.9 * total,
               "per_task": {t: sum(1 for r in results if r.get("task_type") == t and r.get("thinking_fired"))
                            for t in TASKS}}
    (OUT / "parser_verdict.json").write_text(json.dumps(verdict, indent=1))
    if not verdict["pass"]:
        note("PARSER CHECK below 90% bare firing — STOPPING before grid per protocol")
        (OUT / "STOPPED_PARSER_DIVERGENCE").write_text(utcnow())
        sys.exit(3)
    run_grid()


def run_grid():
    # ---- grid: 10 conditions x 4 tasks x 10 samples ----
    grid = LOGS / "grid_turns.jsonl"
    for cond, sysprompt in CONDITIONS:
        tools = TOOLS if cond == "C8" else None
        jobs = [(t, i, p) for t, p in TASKS.items() for i in range(10)]
        t0 = time.time()
        with ThreadPoolExecutor(max_workers=CONC) as ex:
            rows = list(ex.map(
                lambda j: run_turn(grid, "grid", cond, sysprompt, tools, j[0], j[1], j[2]), jobs))
        ok = [r for r in rows if r.get("http_status") == 200]
        f = sum(1 for r in ok if r.get("thinking_fired"))
        note(f"GRID {cond}: fired {f}/{len(ok)} ({round(100*f/max(1,len(ok)))}%) "
             f"in {round(time.time()-t0)}s")
        for t in TASKS:
            tr = [r for r in ok if r.get("task_type") == t]
            note(f"    {t}: {sum(1 for r in tr if r.get('thinking_fired'))}/{len(tr)}")

    # ---- criteria probe: C0 / C4 / C7 x 10 ----
    crit = LOGS / "criteria_turns.jsonl"
    for cond, sysprompt in [("C0", None), ("C4", C4_PERSONA), ("C7", C7)]:
        with ThreadPoolExecutor(max_workers=CONC) as ex:
            rows = list(ex.map(
                lambda i: run_turn(crit, "criteria", cond, sysprompt, None, "criteria", i, CRITERIA_TASK),
                range(10)))
        for r in rows:
            loop_event = (r.get("finish_reason") == "length" and r.get("thinking_fired")
                          and r.get("content_chars", 0) == 0)
            log(LOGS / "criteria_loop_events.jsonl",
                {"condition": cond, "sample": r.get("sample"), "loop_event": loop_event})
        note(f"criteria {cond}: fired {sum(1 for r in rows if r.get('thinking_fired'))}/{len(rows)} "
             f"loops={sum(1 for r in rows if r.get('finish_reason')=='length' and r.get('thinking_fired') and r.get('content_chars',0)==0)}")
    note("qwen gate study COMPLETE")


if __name__ == "__main__":
    main()
