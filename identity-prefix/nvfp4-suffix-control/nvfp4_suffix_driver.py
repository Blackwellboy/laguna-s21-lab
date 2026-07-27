#!/usr/bin/env python3
"""NVFP4 suffix-control replication - 2026-07-27.

WHY: the identity-prefix study (hybrid 3.25bpw, the hybrid lane) found identity at the
TAIL of C6 tripled firing (5/40 -> 18/40, p=0.0026) while identity as a PREFIX
went 0/40. The hybrid-lane interleaved 4-variant suffix control unconfounds
identity-vs-any-30-tokens on the hybrid build. THIS run replicates that exact
4-variant design on the NVFP4 build (NVFP4 lane), the build the published
gate-study curve was measured on. No result is pre-stated anywhere.

DESIGN: mirrors the hybrid suffix-control driver
exactly. Base condition C6 imported byte-identical from the 2026-07-27
gate-study driver. Four tail variants, token-band controlled against the
identity string; filler strings are byte-identical reuses of the hybrid
driver's NEUTRAL and TOPICAL constants (not re-authored). Actual token counts
on THIS lane's tokenizer are verified via /tokenize pre-run and logged to
logs/token_counts.json.

  none            : C6 as published
  suffix_identity : C6 + trained identity appended
  suffix_neutral  : C6 + semantically neutral filler, matched token count
  suffix_topical  : C6 + topically relevant non-identity text, matched count

4 variants x 4 tasks x 10 samples = 160 turns. Single-turn.
Sampling identical to the gate study's recorded settings for this lane:
temp 0.7 / top_p 0.95 / top_k 20, max_tokens 4096, enable_thinking=true.

PROTOCOL: IN-RUN INTERLEAVED. Execution order cycles variants inside every
(sample, task) quartet with a per-quartet shuffled variant order (seeded RNG,
seed logged), so no variant ever runs as a sequential block. conc=1, lane
exclusive: latency is NOT polluted.

Identity string is read at runtime from identity_extracted.txt, which is
extracted verbatim this session from the SERVING checkpoint's
chat_template.jinja on the NVFP4 lane host (not transcribed from any document). The
driver refuses to run if the file is missing or fails the sanity check.
"""
import json, os, random, secrets, sys, time, urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.expanduser("~/gate-study"))
from gate_study_driver import TASKS, C6  # byte-identical import

OUT = Path(os.path.expanduser("~/nvfp4-suffix-control"))
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

# Byte-identical reuse of the hybrid suffix-control driver's fillers.
NEUTRAL = ("The weather in many coastal regions varies quite considerably across "
           "the year. Seasonal patterns often shift gradually and depend on "
           "several entirely unrelated geographic factors.")

TOPICAL = ("Apply the requirements above carefully when preparing every single "
           "answer. Close attention to each listed rule tends to produce much "
           "clearer and more reliable responses.")

VARIANTS = ("none", "suffix_identity", "suffix_neutral", "suffix_topical")
SUFFIX_TEXT = {"suffix_identity": IDENTITY, "suffix_neutral": NEUTRAL,
               "suffix_topical": TOPICAL}


def build_system(variant):
    if variant == "none":
        return C6
    return C6 + "\n" + SUFFIX_TEXT[variant]


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
              "neutral": tokenize_count(NEUTRAL),
              "topical": tokenize_count(TOPICAL)}
    ref = counts["identity"]
    for k in ("identity", "neutral", "topical"):
        counts[f"{k}_dev_pct"] = round(abs(counts[k] - ref) / ref * 100, 1)
    (LOGS / "token_counts.json").write_text(json.dumps(counts, indent=2))
    note(f"token bands: {counts}")
    bad = [k for k in ("neutral", "topical") if counts[f"{k}_dev_pct"] > 5.0]
    if bad:
        note(f"WARNING: token-band deviation >5pct for {bad} on this tokenizer")
    return counts


def chat(messages):
    body = {"model": MODEL, "messages": messages, "max_tokens": MAX_TOKENS,
            "temperature": 0.7, "top_p": 0.95, "top_k": 20,
            "chat_template_kwargs": {"enable_thinking": True}}
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
        "shim_hit": shim_hit,
        "completion_tokens": usage.get("completion_tokens"),
        "prompt_tokens": usage.get("prompt_tokens"),
        "finish_reason": fr,
        "finish_path": path,
        "content_preview": content[:200],
        "reasoning_preview": rc[:200],
    }


def run_turn(logfile, variant, task_type, idx, exec_seq):
    nonce = secrets.token_hex(4)
    messages = [
        {"role": "system", "content": build_system(variant)},
        {"role": "user", "content": f"[run-{nonce}] {TASKS[task_type]}"},
    ]
    status, resp, lat = chat(messages)
    row = {"lane": "nvfp4", "condition": "C6", "variant": variant,
           "task_type": task_type, "sample": idx, "exec_seq": exec_seq,
           "nonce": nonce, "http_status": status, "latency_s": round(lat, 3),
           "concurrency": 1, "latency_polluted": False}
    if status == 200:
        row.update(measure(resp))
    else:
        row["error"] = resp.get("error", "http_" + str(status))
    log(logfile, row)
    note(f"seq={exec_seq} C6/{variant} {task_type} {idx} "
         f"ok={status == 200} fired={row.get('thinking_fired')} "
         f"rtok~{row.get('thinking_tokens_est')} ptok={row.get('prompt_tokens')} "
         f"fr={row.get('finish_reason')} lat={row.get('latency_s')}")
    return status == 200


def build_order(seed):
    """Interleaved: each (sample, task) quartet runs all four variants
    consecutively in a per-quartet shuffled order."""
    rng = random.Random(seed)
    order = []
    for idx in range(SAMPLES):
        for task in TASKS:
            vs = list(VARIANTS)
            rng.shuffle(vs)
            for v in vs:
                order.append((v, task, idx))
    return order


def grid():
    logfile = LOGS / "suffix_nvfp4.jsonl"
    seedfile = LOGS / "order_seed_nvfp4.json"
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
                    done.add((r["variant"], r["task_type"], r["sample"]))
            except Exception:
                pass
    note(f"nvfp4 suffix-control grid: {len(order) - len(done)} turns to run "
         f"({len(done)} already done), order seed {seed}, interleaved, conc=1")
    errors = 0
    for seq, (v, t, i) in enumerate(order):
        if (v, t, i) in done:
            continue
        if not run_turn(logfile, v, t, i, seq):
            errors += 1
            time.sleep(5)
    note(f"nvfp4 suffix-control grid COMPLETE errors={errors}")
    return 0


if __name__ == "__main__":
    sys.exit(grid())
