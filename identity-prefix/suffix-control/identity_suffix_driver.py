#!/usr/bin/env python3
"""Identity SUFFIX control experiment - 2026-07-27.

WHY: the identity-prefix study found identity at the TAIL of C6 tripled firing
(5/40 -> 18/40, p=0.0026). That result is confounded: it cannot distinguish
"the identity sentence at the end restores firing" from "roughly 30 tokens of
any text at the end restores firing". This run unconfounds it.

DESIGN: base condition C6 (imported byte-identical from the 2026-07-27
gate-study driver). Four tail variants, token-band controlled against the
identity string (29/28 tokens on the laguna/qwen tokenizers, matched suffixes
28/28 and 28/27, max deviation 3.6 percent, verified via /tokenize on both
serving lanes before the run):

  none            : C6 as published (replicates the 5/40 cell)
  suffix_identity : C6 + trained identity appended (replicates the 18/40 cell)
  suffix_neutral  : C6 + semantically neutral filler, matched token count
  suffix_topical  : C6 + topically relevant non-identity text, matched count

4 variants x 4 tasks x 10 samples = 160 turns per lane. Laguna 3.25bpw hybrid
primary (gated), Qwen 3.6 35B-A3B NVFP4 control (ungated). Single-turn.

PROTOCOL: IN-RUN INTERLEAVED. The execution order cycles variants inside
every (sample, task) quartet with a per-quartet shuffled variant order
(seeded RNG, seed logged), so no variant ever runs as a sequential block.
This is the mandatory fix for the between-run drift caveat (conn_orig 1/40
vs 7/40 on byte-identical prompts) and the sequential-block caveat carried
by the identity-prefix study itself.

Identity string extracted verbatim this session from the SERVING checkpoint
chat_template.jinja on the lane host (0xSero/Laguna-S-2.1-Hybrid-3.25bpw
snapshot ecd9d39b, md5 9d5abbf83510d99e20a72fdeb1f155e2, byte-identical to
poolside/Laguna-S-2.1-NVFP4's template).

Lanes verified up and idle before start (0 running / 0 waiting on both).
conc=1 per lane, lanes on separate hosts: latency is NOT polluted this run.
"""
import json, os, random, secrets, sys, time, urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.expanduser("~/gate-study"))
from gate_study_driver import TASKS, C6  # byte-identical import

OUT = Path(os.path.expanduser("~/suffix-control"))
LOGS = OUT / "logs"
LOGS.mkdir(parents=True, exist_ok=True)

MAX_TOKENS = 4096
SAMPLES = 10

# Verbatim from the serving checkpoint chat_template.jinja (see docstring).
IDENTITY = ("You are a helpful, conversationally-fluent assistant made by "
            "Poolside. You are here to be helpful to users through natural "
            "language conversations.")

# Token-band-matched controls (verified via /tokenize on both lanes pre-run).
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


LANES = {
    "laguna": {"endpoint": "http://localhost:8101/v1",
               "model": "laguna-s-2.1-tr3-hybrid",
               "temperature": 0.7, "top_p": 0.95, "top_k": 20},
    "qwen": {"endpoint": "http://localhost:8100/v1",
             "model": "nvidia/Qwen3.6-35B-A3B-NVFP4",
             "temperature": 1.0, "top_p": 0.95, "top_k": 20},
}


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def log(path, obj):
    obj = dict(obj)
    obj.setdefault("ts", utcnow())
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def note(msg):
    print(f"[{utcnow()}] {msg}", flush=True)


def clean_content(content):
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


def run_turn(logfile, lane, variant, task_type, idx, exec_seq):
    nonce = secrets.token_hex(4)
    messages = [
        {"role": "system", "content": build_system(variant)},
        {"role": "user", "content": f"[run-{nonce}] {TASKS[task_type]}"},
    ]
    status, resp, lat = chat(lane, messages)
    row = {"lane": lane, "condition": "C6", "variant": variant,
           "task_type": task_type, "sample": idx, "exec_seq": exec_seq,
           "nonce": nonce, "http_status": status, "latency_s": round(lat, 3),
           "latency_polluted": False}
    if status == 200:
        row.update(measure(resp))
    else:
        row["error"] = resp.get("error", "http_" + str(status))
    log(logfile, row)
    note(f"{lane} seq={exec_seq} C6/{variant} {task_type} {idx} "
         f"ok={status == 200} fired={row.get('thinking_fired')} "
         f"rtok~{row.get('thinking_tokens_est')} ptok={row.get('prompt_tokens')} "
         f"fr={row.get('finish_reason')} lat={row.get('latency_s')}")
    return status == 200


def build_order(seed):
    """Interleaved execution order: for each (sample, task) quartet, all four
    variants run consecutively in a per-quartet shuffled order. No variant
    ever forms a sequential block longer than one turn."""
    rng = random.Random(seed)
    order = []
    for idx in range(SAMPLES):
        for task in TASKS:
            vs = list(VARIANTS)
            rng.shuffle(vs)
            for v in vs:
                order.append((v, task, idx))
    return order


def grid(lane):
    logfile = LOGS / f"suffix_{lane}.jsonl"
    seedfile = LOGS / f"order_seed_{lane}.json"
    if seedfile.exists():
        seed = json.loads(seedfile.read_text())["seed"]
    else:
        seed = secrets.randbits(32)
        seedfile.write_text(json.dumps({"seed": seed, "created": utcnow()}))
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
    note(f"{lane} suffix-control grid: {len(order) - len(done)} turns to run "
         f"({len(done)} already done), order seed {seed}, interleaved")
    errors = 0
    for seq, (v, t, i) in enumerate(order):
        if (v, t, i) in done:
            continue
        if not run_turn(logfile, lane, v, t, i, seq):
            errors += 1
            time.sleep(5)
    note(f"{lane} suffix-control grid COMPLETE errors={errors}")
    return 0


if __name__ == "__main__":
    sys.exit(grid(sys.argv[1]))
