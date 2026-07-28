#!/usr/bin/env python3
"""Prompt-topology study — 2026-07-30 (fable).

Hypothesis under test (community reader, via gate-study thread): prompt FORMAT
("topology") acts as a latent/undocumented control on thinking-gate firing,
independent of semantic content and length. Our own grid rhymes: firing is
non-monotonic in instruction count (C6 dense 10-rule block 3/40 vs the much
longer C7 agent prompt 24/40), so length alone is not the variable.

Design:
  - ONE fixed requirement set (8 requirements, wording identical across
    variants) rendered in 5 topologies:
      prose / bullets / numbered / json / dialogue
  - Length controlled: preflight tokenizes every block on BOTH lanes and the
    run refuses to start unless all 5 blocks sit within +/-10% of the
    per-lane mean (reversed variants measured too). Actual per-variant token
    counts reported in token_band.json.
  - Ordering control: original vs reversed requirement order on the two most
    informative topologies (chosen after the main grid; `order` phase).
  - Apparatus: bare (no system prompt) vs C7 full agent prompt (imported
    byte-identical from the 2026-07-27 gate-study driver).
  - 4 task types byte-identical (imported), 10 samples/cell, nonce-prefixed,
    thinking enabled, ceiling 4096, model-card sampling per lane.
  - Both lanes: spark-node-b :8101 Laguna hybrid (gated) + spark-node-a :8100 Qwen
    (ungated). Single-turn THROUGHOUT — per the §3a standing rule this study
    is therefore unaffected by the multi-turn reasoning-stripping mechanism.
  - Laguna stray leading '</think>' leak cleaned per context-mass driver shim;
    occurrences recorded per turn (shim_hit).
  - Concurrency: firing is not latency-sensitive (same justification as the
    2026-07-28 Qwen study's CONC=4); latency_s is recorded but flagged
    non-comparable across lanes/conc.

Usage:
  python3 prompt_topology_driver.py preflight
  python3 prompt_topology_driver.py grid laguna|qwen
  python3 prompt_topology_driver.py order laguna|qwen topo1,topo2
"""
import json, os, secrets, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

sys.path.insert(0, "../gate-study")
from gate_study_driver import TASKS, C7  # byte-identical tasks + agent prompt

OUT = Path(".")
LOGS = OUT / "logs"
LOGS.mkdir(parents=True, exist_ok=True)

MAX_TOKENS = 4096
SAMPLES = 10
BAND = 0.10

LANES = {
    "laguna": {"endpoint": "http://localhost:8101/v1",
               "model": "laguna-s-2.1-tr3-hybrid",
               "temperature": 0.7, "top_p": 0.95, "top_k": 20, "conc": 3},
    "qwen": {"endpoint": "http://localhost:8100/v1",
             "model": "nvidia/Qwen3.6-35B-A3B-NVFP4",
             "temperature": 1.0, "top_p": 0.95, "top_k": 20, "conc": 4},
}

# ---- the ONE fixed requirement set (wording identical in every topology) ----
REQS = [
    "be direct and concise in everything you write",
    "state your assumptions explicitly rather than leaving them implicit",
    "cite concrete evidence for every claim and never invent citations or numbers",
    "answer the question that was actually asked before adding any caveats",
    "use plain language with no filler words",
    "if you are uncertain, say so and give your best estimate",
    "keep code idiomatic and comment only where something is non-obvious",
    "keep the answer under 400 words unless the task genuinely requires more",
]
LEAD = ("Before answering, follow these requirements throughout your entire "
        "response.")
CLOSE = "These requirements apply to the whole of your answer."


def _cap(s):
    return s[0].upper() + s[1:]


def block_prose(reqs):
    # connectives are semantically null padding, used only to hold the
    # token band (see token_band.json)
    parts = []
    for i, r in enumerate(reqs):
        conn = "You must " if i == 0 else "In addition, you must "
        parts.append(conn + r + ".")
    return f"{LEAD} " + " ".join(parts) + f" {CLOSE}"


def block_bullets(reqs):
    body = "\n".join("- You must " + r + "." for r in reqs)
    return f"{LEAD}\n{body}\n{CLOSE}"


def block_numbered(reqs):
    body = "\n".join(f"{i+1}. You must {r}." for i, r in enumerate(reqs))
    return f"{LEAD}\n{body}\n{CLOSE}"


def block_json(reqs):
    obj = {"instruction": LEAD,
           "requirements": ["you must " + r for r in reqs],
           "scope": CLOSE}
    return json.dumps(obj, separators=(", ", ": "))


def block_dialogue(reqs):
    lines = ["OP: " + LEAD]
    for r in reqs:
        lines.append("OP: You must " + r + ".")
    lines.append("OP: " + CLOSE)
    return "\n".join(lines)


TOPOLOGIES = {
    "prose": block_prose,
    "bullets": block_bullets,
    "numbered": block_numbered,
    "json": block_json,
    "dialogue": block_dialogue,
}


def build_block(topo, order="original"):
    reqs = list(REQS) if order == "original" else list(reversed(REQS))
    return TOPOLOGIES[topo](reqs)


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


def tokenize(lane, text):
    cfg = LANES[lane]
    body = {"model": cfg["model"], "prompt": text}
    req = urllib.request.Request(
        f"{cfg['endpoint'].removesuffix('/v1')}/tokenize",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)["count"]


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


def run_turn(logfile, lane, phase, topo, order, apparatus, task_type, idx):
    nonce = secrets.token_hex(4)
    block = build_block(topo, order)
    messages = []
    if apparatus == "c7":
        messages.append({"role": "system", "content": C7})
    messages.append({"role": "user",
                     "content": f"[run-{nonce}] {block}\n\n{TASKS[task_type]}"})
    status, resp, lat = chat(lane, messages)
    row = {"lane": lane, "phase": phase, "topology": topo, "order": order,
           "apparatus": apparatus, "task_type": task_type, "sample": idx,
           "nonce": nonce, "http_status": status, "latency_s": round(lat, 3)}
    if status == 200:
        row.update(measure(resp))
    else:
        row["error"] = resp.get("error", "http_" + str(status))
    log(logfile, row)
    note(f"{lane} {phase} {topo}/{order}/{apparatus} {task_type} {idx} "
         f"ok={status == 200} fired={row.get('thinking_fired')} "
         f"rtok~{row.get('thinking_tokens_est')} fr={row.get('finish_reason')} "
         f"lat={row.get('latency_s')}")
    return row


def preflight():
    """Tokenize every block on both lanes; enforce the +/-10% band."""
    report = {"band_pct": BAND * 100, "lanes": {}}
    ok = True
    for lane in LANES:
        rows = {}
        for topo in TOPOLOGIES:
            for order in ("original", "reversed"):
                rows[f"{topo}/{order}"] = tokenize(lane, build_block(topo, order))
        originals = {k: v for k, v in rows.items() if k.endswith("/original")}
        mean = sum(originals.values()) / len(originals)
        lo, hi = mean * (1 - BAND), mean * (1 + BAND)
        verdict = {k: (lo <= v <= hi) for k, v in originals.items()}
        lane_ok = all(verdict.values())
        ok = ok and lane_ok
        report["lanes"][lane] = {
            "block_tokens": rows, "originals_mean": round(mean, 1),
            "band_lo": round(lo, 1), "band_hi": round(hi, 1),
            "in_band": verdict, "lane_ok": lane_ok,
        }
        note(f"{lane}: mean={mean:.1f} band=[{lo:.1f},{hi:.1f}] "
             + " ".join(f"{k}={v}" for k, v in rows.items()))
    (OUT / "token_band.json").write_text(json.dumps(report, indent=1))
    note(f"PREFLIGHT {'PASS' if ok else 'FAIL'} — token_band.json written")
    return 0 if ok else 2


def grid(lane):
    band = json.loads((OUT / "token_band.json").read_text())
    if not band["lanes"][lane]["lane_ok"]:
        note(f"REFUSING grid: {lane} token band failed")
        return 2
    logfile = LOGS / f"grid_{lane}.jsonl"
    cells = [(topo, app, task, i)
             for topo in TOPOLOGIES
             for app in ("bare", "c7")
             for task in TASKS
             for i in range(SAMPLES)]
    note(f"{lane} grid: {len(cells)} turns conc={LANES[lane]['conc']}")
    with ThreadPoolExecutor(max_workers=LANES[lane]["conc"]) as ex:
        futs = [ex.submit(run_turn, logfile, lane, "grid", topo, "original",
                          app, task, i) for topo, app, task, i in cells]
        for f in futs:
            f.result()
    note(f"{lane} grid COMPLETE")
    return 0


def order_phase(lane, topos):
    logfile = LOGS / f"order_{lane}.jsonl"
    cells = [(topo, app, task, i)
             for topo in topos
             for app in ("bare", "c7")
             for task in TASKS
             for i in range(SAMPLES)]
    note(f"{lane} order phase: topos={topos} {len(cells)} turns")
    with ThreadPoolExecutor(max_workers=LANES[lane]["conc"]) as ex:
        futs = [ex.submit(run_turn, logfile, lane, "order", topo, "reversed",
                          app, task, i) for topo, app, task, i in cells]
        for f in futs:
            f.result()
    note(f"{lane} order COMPLETE")
    return 0


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "preflight":
        sys.exit(preflight())
    elif cmd == "grid":
        sys.exit(grid(sys.argv[2]))
    elif cmd == "order":
        sys.exit(order_phase(sys.argv[2], sys.argv[3].split(",")))
    else:
        sys.exit("unknown phase")
