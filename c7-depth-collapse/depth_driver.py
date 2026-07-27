#!/usr/bin/env python3
"""C7 depth-collapse follow-up - 2026-07-27.

WHY: two confirmed cases show interventions that raise/hold thinking FIRING
while collapsing DEPTH: tools C7->C8 (60->72 pct firing, 740->282 median
reasoning-token est) and identity-anywhere at C7 (17 -> 17-24/40 firing,
1080 -> 120-200 rtok). Tail-composition controls also showed depth varying
by suffix type (identity 656 / neutral 809 / topical 1015 among fired).
QUESTION: what controls reasoning DEPTH, as distinct from firing?

DESIGN (depth is the dependent variable, so all cells are chosen to FIRE at
usable rates; base = C7, which fires ~17-24/40 on this lane):

  c7_bare           : gate-study C7 verbatim (depth baseline, expect ~1080)
  c7_identity       : C7 + trained identity appended (suffix, newline-joined)
  c7_neutral        : C7 + neutral filler suffix, token-matched to identity
  c7_tools          : C7 + the gate-study TOOLS schemas in the request (== C8)
  c7_identity_tools : identity suffix AND tool schemas (do suppressors stack?)

5 arms x 4 tasks x 10 samples = 200 turns, single-turn each.
Sampling identical to the gate study's recorded settings for this lane:
temp 0.7 / top_p 0.95 / top_k 20, max_tokens 4096, enable_thinking=true.

PROTOCOL: IN-RUN INTERLEAVED. Execution order cycles all five arms inside
every (sample, task) quintet with a per-quintet shuffled arm order (seeded
RNG, seed logged), so no arm ever runs as a sequential block. conc=1, lane
exclusive. Apparatus strings are imported byte-identical from the published
gate-study driver (C7, TOOLS, TASKS); the neutral filler is the byte-identical
NEUTRAL constant from the hybrid / NVFP4 suffix-control drivers. The identity
string is read from identity_extracted.txt, extracted verbatim THIS session
from the serving checkpoint's chat_template.jinja on the serving host (md5 of
the serving template verified against 9d5abbf83510d99e20a72fdeb1f155e2
pre-run); the driver refuses to run if the file is missing or fails the
sanity check.

ANALYSIS PLAN (pre-stated): primary = median thinking_tokens_est among FIRED
rows per arm, with n-fired stated (depth medians on small n-fired are
fragile; always report the n). Secondary = firing rates. Question of record:
does depth suppression compose additively (identity+tools < tools alone) or
floor (identity+tools ~= tools alone)?
"""
import json, os, random, secrets, sys, time, urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.expanduser("~/gate-study"))
from gate_study_driver import TASKS, C7, TOOLS  # byte-identical import

OUT = Path(os.path.expanduser("~/c7-depth-collapse"))
LOGS = OUT / "logs"
LOGS.mkdir(parents=True, exist_ok=True)

ENDPOINT = os.environ.get("LAGUNA_ENDPOINT", "http://localhost:8000/v1")
MODEL = "poolside/Laguna-S-2.1-NVFP4"
MAX_TOKENS = 4096
SAMPLES = 10

IDENTITY_FILE = OUT / "identity_extracted.txt"
if not IDENTITY_FILE.exists():
    sys.exit("FATAL: identity_extracted.txt missing (must be extracted from "
             "the serving checkpoint template this session)")
IDENTITY = IDENTITY_FILE.read_text(encoding="utf-8").strip()
if not IDENTITY.endswith("natural language conversations."):
    sys.exit("FATAL: identity string failed sanity check")

# Byte-identical reuse of the hybrid / NVFP4 suffix-control drivers' filler.
NEUTRAL = ("The weather in many coastal regions varies quite considerably across "
           "the year. Seasonal patterns often shift gradually and depend on "
           "several entirely unrelated geographic factors.")

ARMS = ("c7_bare", "c7_identity", "c7_neutral", "c7_tools", "c7_identity_tools")
SUFFIX = {"c7_identity": IDENTITY, "c7_neutral": NEUTRAL,
          "c7_identity_tools": IDENTITY}
HAS_TOOLS = {"c7_tools", "c7_identity_tools"}


def build_system(arm):
    if arm in SUFFIX:
        return C7 + "\n" + SUFFIX[arm]
    return C7


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def log(path, obj):
    obj = dict(obj)
    obj.setdefault("ts", utcnow())
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def note(msg):
    print(f"[{utcnow()}] {msg}", flush=True)


def tokenize_count(text):
    body = {"model": MODEL, "prompt": text}
    req = urllib.request.Request(
        f"{ENDPOINT.rsplit('/v1', 1)[0]}/tokenize", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r).get("count")


def verify_token_bands():
    counts = {"identity": tokenize_count(IDENTITY),
              "neutral": tokenize_count(NEUTRAL)}
    ref = counts["identity"]
    counts["neutral_dev_pct"] = round(abs(counts["neutral"] - ref) / ref * 100, 1)
    (LOGS / "token_counts.json").write_text(json.dumps(counts, indent=2))
    note(f"token bands: {counts}")
    if counts["neutral_dev_pct"] > 5.0:
        note("WARNING: neutral filler token-band deviation >5pct on this tokenizer")
    return counts


def chat(messages, tools):
    body = {"model": MODEL, "messages": messages, "max_tokens": MAX_TOKENS,
            "temperature": 0.7, "top_p": 0.95, "top_k": 20,
            "chat_template_kwargs": {"enable_thinking": True}}
    if tools:
        body["tools"] = tools
    req = urllib.request.Request(
        f"{ENDPOINT}/chat/completions", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=1800) as r:
            return r.status, json.load(r), time.time() - t0
    except Exception as e:
        return None, {"error": str(e)[:300]}, time.time() - t0


def clean_content(content):
    stripped = content.lstrip()
    if stripped.startswith("</think>"):
        return stripped[len("</think>"):].lstrip(), True
    return content, False


def measure(resp):
    ch = (resp.get("choices") or [{}])[0]
    msg = ch.get("message") or {}
    raw_content = msg.get("content") or ""
    content, shim_hit = clean_content(raw_content)
    rc = msg.get("reasoning_content") or msg.get("reasoning") or ""
    tool_calls = msg.get("tool_calls") or []
    usage = resp.get("usage") or {}
    fired = bool(rc)
    ttok = max(1, len(rc) // 4) if rc else 0
    for k in ("reasoning_tokens", "thinking_tokens"):
        if usage.get(k):
            ttok = int(usage[k])
            fired = fired or ttok > 0
    fr = ch.get("finish_reason")
    if fired:
        path = "reasoned_to_ceiling" if fr == "length" else "reasoned_to_answer"
    else:
        path = "no_think_to_ceiling" if fr == "length" else "no_think_to_answer"
    return {
        "thinking_fired": fired,
        "thinking_tokens_est": ttok,
        "reasoning_chars": len(rc),
        "content_chars": len(content),
        "n_tool_calls": len(tool_calls),
        "shim_hit": shim_hit,
        "completion_tokens": usage.get("completion_tokens"),
        "prompt_tokens": usage.get("prompt_tokens"),
        "finish_reason": fr,
        "finish_path": path,
        "content_preview": content[:200],
        "reasoning_preview": rc[:200],
    }


def run_turn(logfile, arm, task_type, idx, exec_seq):
    nonce = secrets.token_hex(4)
    messages = [
        {"role": "system", "content": build_system(arm)},
        {"role": "user", "content": f"[run-{nonce}] {TASKS[task_type]}"},
    ]
    tools = TOOLS if arm in HAS_TOOLS else None
    status, resp, lat = chat(messages, tools)
    row = {"lane": "nvfp4", "condition": "C7", "arm": arm,
           "task_type": task_type, "sample": idx, "exec_seq": exec_seq,
           "nonce": nonce, "http_status": status, "latency_s": round(lat, 3),
           "concurrency": 1, "latency_polluted": False}
    if status == 200:
        row.update(measure(resp))
    else:
        row["error"] = resp.get("error", "http_" + str(status))
    log(logfile, row)
    note(f"seq={exec_seq} {arm} {task_type} {idx} "
         f"ok={status == 200} fired={row.get('thinking_fired')} "
         f"rtok~{row.get('thinking_tokens_est')} ptok={row.get('prompt_tokens')} "
         f"fr={row.get('finish_reason')} lat={row.get('latency_s')}")
    return status == 200


def build_order(seed):
    """Interleaved: each (sample, task) quintet runs all five arms
    consecutively in a per-quintet shuffled order."""
    rng = random.Random(seed)
    order = []
    for idx in range(SAMPLES):
        for task in TASKS:
            arms = list(ARMS)
            rng.shuffle(arms)
            for a in arms:
                order.append((a, task, idx))
    return order


def grid():
    logfile = LOGS / "depth_c7.jsonl"
    seedfile = LOGS / "order_seed_depth.json"
    if seedfile.exists():
        seed = json.loads(seedfile.read_text())["seed"]
    else:
        seed = secrets.randbits(32)
        seedfile.write_text(json.dumps({"seed": seed, "created": utcnow()}))
    verify_token_bands()
    order = build_order(seed)
    done = set()
    if logfile.exists():
        for line in logfile.read_text().splitlines():
            try:
                r = json.loads(line)
                if r.get("http_status") == 200:
                    done.add((r["arm"], r["task_type"], r["sample"]))
            except Exception:
                pass
    note(f"c7 depth grid: {len(order) - len(done)} turns to run "
         f"({len(done)} already done), order seed {seed}, interleaved, conc=1")
    errors = 0
    for seq, (a, t, i) in enumerate(order):
        if (a, t, i) in done:
            continue
        if not run_turn(logfile, a, t, i, seq):
            errors += 1
            time.sleep(5)
    note(f"c7 depth grid COMPLETE errors={errors}")
    return 0


if __name__ == "__main__":
    sys.exit(grid())
