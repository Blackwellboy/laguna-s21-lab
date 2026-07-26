#!/usr/bin/env python3
"""PR #10 replication: HumanEval+ thinking A/B on Laguna S 2.1 NVFP4 rev 0761412.

Design is adapted from offlabel scripts/thinking-probes/thinking_ab.py (merged
PR #6). Adaptations from that tool, each with a reason (documented for the
methodology section):

1. ARMS: explicit {"enable_thinking": true} vs {"enable_thinking": false} only.
   The "absent" arm is dropped: absent == ON on this revision (offlabel #5),
   and PR #10's claim is a true-vs-false comparison.
2. NONCE: thinking_ab appends "(ref N)" to the prompt to defeat prefix caches.
   Here the prompt is the benchmark item and MUST stay byte-identical to
   HumanEval+, so no nonce. Instead: vLLM per-request `seed` varies sampling,
   and vLLM prefix caching is exact-KV reuse (identical logits, saves prefill
   compute only) - it cannot serve a stale reply the way llama.cpp
   cache_prompt can, so the confound the nonce guards against does not exist
   on this stack. cache_prompt is a llama.cpp knob and is not sent.
3. INTERLEAVING: kept. Submission order is (seed, problem, [ON, OFF]) so the
   two arms of every (problem, seed) pair are adjacent and share any drift.
   Requests run through a small thread pool; in-flight windows always contain
   both arms.
4. FIELD NAMES: reads message.reasoning_content AND message.reasoning (this
   stack's poolside_v1 parser emits `reasoning`; the runner-bug session showed
   reading only one field undercounts). Verdict logic otherwise identical.
5. CONTROL CELL: the OFF arm is the structural control - reasoning must be
   ~absent there. Reported per arm; if OFF shows reasoning the instrument is
   broken (thinking-probes README rule).
6. MAX_TOKENS: 12288 both arms, fixed, no budget retry (tests apollo-mg's
   p95-derived ceiling directly). No retry of any kind on HTTP 200; one retry
   only on transport-level errors (connection reset), logged as such.
7. SAMPLING: temperature 0.7, top_p 0.95, top_k 20 - the model's recommended
   sampling per the serve script's --override-generation-config, IDENTICAL
   across arms (this removes Apollo's t0.7-vs-t0.6 confound). 3 seeds per
   (problem, arm). Sent explicitly per request so the A/B does not depend on
   server defaults.
8. PROMPT: evalplus's canonical chat instruction_prefix, user message only,
   no system prompt (the C0 cell). No assistant response-prefill (evalplus's
   _MAGIC_SPLITTER_ prefill trick is incompatible with a thinking arm).

Outputs: raw_turns.jsonl (every response in full), samples_{arm}_s{seed}.jsonl
(evalplus format), progress to stdout.
"""

import argparse, json, re, time, zlib
import urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Lock

from evalplus.data import get_human_eval_plus

INSTRUCTION = ("Please provide a self-contained Python script that solves the "
               "following problem in a markdown code block:")
THINK_MARKER = re.compile(r"</?think>", re.I)
FENCE = re.compile(r"```python\s*\n(.*?)```", re.S)

ARMS = {"on": {"enable_thinking": True}, "off": {"enable_thinking": False}}
SAMPLING = {"temperature": 0.7, "top_p": 0.95, "top_k": 20}
MAX_TOKENS = 12288


def build_prompt(task_prompt: str) -> str:
    return f"{INSTRUCTION}\n```\n{task_prompt.strip()}\n```\n"


def compression_ratio(text: str, tail: int = 4000) -> float:
    t = text[-tail:].encode()
    if not t:
        return 0.0
    return len(t) / max(len(zlib.compress(t, 9)), 1)


def one_request(base, model, prompt, arm, seed, timeout):
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": MAX_TOKENS,
        "seed": seed,
        "chat_template_kwargs": ARMS[arm],
        **SAMPLING,
    }
    req = urllib.request.Request(
        base + "/v1/chat/completions", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"})
    transport_retries = 0
    while True:
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                d = json.load(r)
            break
        except urllib.error.HTTPError as e:
            return {"error": f"HTTP {e.code}: {e.read()[:300]}",
                    "seconds": round(time.time() - t0, 1),
                    "transport_retries": transport_retries}
        except Exception as e:  # noqa: BLE001  transport-level
            if transport_retries >= 1:
                return {"error": f"TRANSPORT: {type(e).__name__}: {e}",
                        "seconds": round(time.time() - t0, 1),
                        "transport_retries": transport_retries}
            transport_retries += 1
            time.sleep(5)
    dt = round(time.time() - t0, 1)
    ch = d["choices"][0]
    msg = ch["message"]
    content = msg.get("content") or ""
    reasoning = (msg.get("reasoning_content") or msg.get("reasoning") or "")
    usage = d.get("usage", {})
    finish = ch.get("finish_reason")
    m = FENCE.search(content)
    extractable = bool(m and m.group(1).strip())
    cap_hit = finish == "length"
    row = {
        "seconds": dt, "finish_reason": finish, "cap_hit": cap_hit,
        "content": content, "reasoning": reasoning,
        "reasoning_chars": len(reasoning), "content_chars": len(content),
        "completion_tokens": usage.get("completion_tokens"),
        "prompt_tokens": usage.get("prompt_tokens"),
        "thinking_fired": bool(reasoning.strip()) or bool(THINK_MARKER.search(content)),
        "think_marker_in_content": bool(THINK_MARKER.search(content)),
        "extractable": extractable,
        "transport_retries": transport_retries,
    }
    if cap_hit:
        row["tail_compression_ratio"] = round(
            compression_ratio(reasoning + content), 2)
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--model", default="poolside/Laguna-S-2.1-NVFP4")
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--concurrency", type=int, default=16)
    ap.add_argument("--timeout", type=int, default=2400)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--limit", type=int, default=0, help="debug: first N problems")
    args = ap.parse_args()

    out = Path(args.outdir); out.mkdir(parents=True, exist_ok=True)
    problems = get_human_eval_plus()
    ids = list(problems)
    if args.limit:
        ids = ids[:args.limit]

    plan = []
    for s in range(args.seeds):
        for i, tid in enumerate(ids):
            for arm in ("on", "off"):
                plan.append((tid, i, s, arm))
    print(f"{len(ids)} problems x {args.seeds} seeds x 2 arms = {len(plan)} requests")

    raw_path = out / "raw_turns.jsonl"
    done = set()
    if raw_path.exists():
        for line in raw_path.read_text().splitlines():
            r = json.loads(line)
            done.add((r["task_id"], r["seed"], r["arm"]))
        print(f"resuming: {len(done)} already done")

    lock = Lock()
    fh = open(raw_path, "a")
    counters = {"done": len(done)}

    def work(item):
        tid, i, s, arm = item
        if (tid, s, arm) in done:
            return
        seed = 10_000 * s + i          # same seed for both arms of a pair
        prompt = build_prompt(problems[tid]["prompt"])
        row = one_request(args.base, args.model, prompt, arm, seed, args.timeout)
        row.update({"task_id": tid, "arm": arm, "seed": s, "vllm_seed": seed})
        with lock:
            fh.write(json.dumps(row) + "\n"); fh.flush()
            counters["done"] += 1
            n = counters["done"]
            if "error" in row:
                print(f"[{n}/{len(plan)}] {tid} {arm} s{s} ERROR {row['error'][:120]}", flush=True)
            else:
                print(f"[{n}/{len(plan)}] {tid} {arm} s{s} "
                      f"fired={row['thinking_fired']} cap={row['cap_hit']} "
                      f"extract={row['extractable']} ctok={row['completion_tokens']} "
                      f"{row['seconds']}s", flush=True)

    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        list(ex.map(work, plan))
    fh.close()

    # emit evalplus sample files per (arm, seed)
    rows = [json.loads(l) for l in raw_path.read_text().splitlines()]
    for arm in ("on", "off"):
        for s in range(args.seeds):
            sel = [r for r in rows if r["arm"] == arm and r["seed"] == s
                   and "error" not in r]
            p = out / f"samples_{arm}_s{s}.jsonl"
            with open(p, "w") as f:
                for r in sorted(sel, key=lambda r: int(r["task_id"].split("/")[1])):
                    f.write(json.dumps({"task_id": r["task_id"],
                                        "solution": r["content"]}) + "\n")
            print(f"wrote {p} ({len(sel)} samples)")
    print("DONE")


if __name__ == "__main__":
    main()
