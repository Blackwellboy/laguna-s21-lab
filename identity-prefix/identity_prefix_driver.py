#!/usr/bin/env python3
"""Identity-prefix study - 2026-07-30.

Hypothesis (community wire-level report): thinking collapse under long system
prompts is driven by EVICTION OF THE TRAINED IDENTITY PREFIX, not by
instruction load. Reported: no-sys 8/8 fired, helpful-assistant 6/6, 40K agent
prompt 0/8, same 40K prompt with the trained identity sentence as literal
first line 6-7/8, identity spliced mid-sentence 1/6, identity + extra sentence
after 4/6. "Pure prefix prior."

Test against our published grid: C6 (10-rule block, 3/40 crater) and C7 (full
agent prompt, 24/40), imported BYTE-IDENTICAL from the 2026-07-27 gate-study
driver. Four variants each:
  published : condition text as published
  prefix    : trained identity prepended as the literal first line
  suffix    : identity appended at the END instead
  spliced   : identity present at front but spliced mid-sentence w/ extra words

8 cells per lane x 4 task types (byte-identical) x 10 samples = 320 turns/lane.
Both lanes: Laguna 3.25bpw hybrid (gated) + Qwen
(ungated control; its template has NO default system message).
SINGLE-TURN THROUGHOUT - the multi-turn reasoning-stripping mechanism is
ruled out as a confound by design.
Thinking enabled, ceiling 4096, model-card sampling, nonce-prefixed.

CONTENTION MODE: another study (prompt_topology_20260730) is live on both
lanes at conc 3/4; its driver has no pause point, so this study runs DEGRADED
at conc=1 per lane. latency_s is POLLUTED / non-comparable. Firing is not
latency-sensitive (standing rationale from the 2026-07-28 Qwen study).

Identity string extracted verbatim from the serving checkpoint
chat_template.jinja (0xSero/Laguna-S-2.1-Hybrid-3.25bpw @ ecd9d39b, md5
9d5abbf83510d99e20a72fdeb1f155e2, byte-identical to
poolside/Laguna-S-2.1-NVFP4).
"""
import json, os, secrets, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

sys.path.insert(0, os.path.expanduser("~/gate-study"))
from gate_study_driver import TASKS, C6, C7  # byte-identical

OUT = Path(os.path.expanduser("~/identity-prefix"))
LOGS = OUT / "logs"
LOGS.mkdir(parents=True, exist_ok=True)

MAX_TOKENS = 4096
SAMPLES = 10

# Verbatim from chat_template.jinja default system_message (both builds identical)
IDENTITY = ("You are a helpful, conversationally-fluent assistant made by "
            "Poolside. You are here to be helpful to users through natural "
            "language conversations.")

# Identity present but interrupted mid-first-sentence by inserted words
IDENTITY_SPLICED = ("You are a helpful, conversationally-fluent assistant, "
                    "one who follows the requirements given below carefully, "
                    "made by Poolside. You are here to be helpful to users "
                    "through natural language conversations.")

CONDITIONS = {"C6": C6, "C7": C7}
VARIANTS = ("published", "prefix", "suffix", "spliced")


def build_system(cond_text, variant):
    if variant == "published":
        return cond_text
    if variant == "prefix":
        return IDENTITY + "\n" + cond_text
    if variant == "suffix":
        return cond_text + "\n" + IDENTITY
    if variant == "spliced":
        return IDENTITY_SPLICED + "\n" + cond_text
    raise ValueError(variant)


LANES = {
    "laguna": {"endpoint": "http://localhost:8101/v1",
               "model": "laguna-s-2.1-tr3-hybrid",
               "temperature": 0.7, "top_p": 0.95, "top_k": 20, "conc": 1},
    "qwen": {"endpoint": "http://localhost:8100/v1",
             "model": "nvidia/Qwen3.6-35B-A3B-NVFP4",
             "temperature": 1.0, "top_p": 0.95, "top_k": 20, "conc": 1},
}


def utcnow():
    return datetime.now(timezone.utc).isoformat()


_loglock = Lock()


def log(path, obj):
    obj = dict(obj)
    obj.setdefault("ts", utcnow())
    with _loglock:
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def note(msg):
    print(f"[{utcnow()}] {msg}", flush=True)


def clean_content(content):
    """Strip the Laguna lane's known stray leading '</think>' leak."""
    stripped = content.lstrip()
    if stripped.startswith("</think>"):
        return stripped[len("</think>"):].lstrip(), True
    return content, False


def chat(lane, messages):
    cfg = LANES[lane]
    body = {
        "model": cfg["model"], "messages": messages, "max_tokens": MAX_TOKENS,
        "temperature": cfg["temperature"], "top_p": cfg["top_p"],
        "top_k": cfg["top_k"],
        "chat_template_kwargs": {"enable_thinking": True},
    }
    req = urllib.request.Request(
        f"{cfg['endpoint']}/chat/completions", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=1800) as r:
            return r.status, json.load(r), time.time() - t0
    except Exception as e:
        return None, {"error": str(e)[:300]}, time.time() - t0


def measure(resp):
    ch = (resp.get("choices") or [{}])[0]
    msg = ch.get("message") or {}
    raw_content = msg.get("content") or ""
    content, shim_hit = clean_content(raw_content)
    rc = msg.get("reasoning_content") or msg.get("reasoning") or ""
    usage = resp.get("usage") or {}
    fired = bool(rc)
    ttok = max(1, len(rc) // 4) if rc else 0
    for k in ("reasoning_tokens", "thinking_tokens"):
        if usage.get(k):
            ttok = int(usage[k])
            fired = fired or ttok > 0
    fr = ch.get("finish_reason")
    has_tools = bool(msg.get("tool_calls"))
    if fired:
        path = ("reasoned_to_ceiling" if fr == "length"
                else "reasoned_then_tool_called" if has_tools
                else "reasoned_to_answer")
    else:
        path = ("no_think_to_ceiling" if fr == "length"
                else "no_think_tool_called" if has_tools
                else "no_think_to_answer")
    return {
        "thinking_fired": fired,
        "thinking_tokens_est": ttok,
        "reasoning_chars": len(rc),
        "content_chars": len(content),
        "shim_hit": shim_hit,
        "completion_tokens": usage.get("completion_tokens"),
        "prompt_tokens": usage.get("prompt_tokens"),
        "finish_reason": fr,
        "finish_path": path,
        "has_tool_calls": has_tools,
        "content_preview": content[:200],
        "reasoning_preview": rc[:200],
    }


def run_turn(logfile, lane, cond, variant, task_type, idx):
    nonce = secrets.token_hex(4)
    messages = [
        {"role": "system", "content": build_system(CONDITIONS[cond], variant)},
        {"role": "user", "content": f"[run-{nonce}] {TASKS[task_type]}"},
    ]
    status, resp, lat = chat(lane, messages)
    row = {"lane": lane, "condition": cond, "variant": variant,
           "task_type": task_type, "sample": idx, "nonce": nonce,
           "http_status": status, "latency_s": round(lat, 3),
           "latency_polluted": True}
    if status == 200:
        row.update(measure(resp))
    else:
        row["error"] = resp.get("error", "http_" + str(status))
    log(logfile, row)
    note(f"{lane} {cond}/{variant} {task_type} {idx} ok={status == 200} "
         f"fired={row.get('thinking_fired')} rtok~{row.get('thinking_tokens_est')} "
         f"ptok={row.get('prompt_tokens')} fr={row.get('finish_reason')} "
         f"lat={row.get('latency_s')}")
    return row


def grid(lane):
    logfile = LOGS / f"identity_{lane}.jsonl"
    done = set()
    if logfile.exists():
        for line in logfile.read_text().splitlines():
            try:
                r = json.loads(line)
                if r.get("http_status") == 200:
                    done.add((r["condition"], r["variant"],
                              r["task_type"], r["sample"]))
            except Exception:
                pass
    cells = [(c, v, t, i)
             for c in CONDITIONS
             for v in VARIANTS
             for t in TASKS
             for i in range(SAMPLES)
             if (c, v, t, i) not in done]
    note(f"{lane} identity grid: {len(cells)} turns to run "
         f"({len(done)} already done) conc={LANES[lane]['conc']}")
    with ThreadPoolExecutor(max_workers=LANES[lane]["conc"]) as ex:
        futs = [ex.submit(run_turn, logfile, lane, c, v, t, i)
                for c, v, t, i in cells]
        for f in futs:
            f.result()
    note(f"{lane} identity grid COMPLETE")
    return 0


if __name__ == "__main__":
    sys.exit(grid(sys.argv[1]))
