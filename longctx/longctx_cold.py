#!/usr/bin/env python3
"""Laguna COLD long-context probe (Hermes tuning campaign 2026-07-23).

Method statement: prefix-cache reuse is defeated by putting a unique random
nonce as the FIRST line of every prompt (vLLM prefix caching hashes blocks
from position 0, so a differing first block invalidates all reuse). Every
timed run is therefore a cold prefill even with --enable-prefix-caching on.
One service restart is additionally performed before the battery (by the
operator/driver, not this script).

Per timed run we record: prompt_tokens, TTFT (= queue+prefill+first step),
decode tok/s = (completion_tokens-1)/(t_last-t_first), total wall, needle
retrieval, and a /metrics KV-usage sample taken DURING decode.
"""
import json
import os
import random
import string
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

BASE = os.environ.get("HERMES_BENCH_BASE", "http://localhost:8000/v1")
METRICS = BASE.rsplit("/v1", 1)[0] + "/metrics"
MODEL = "poolside/Laguna-S-2.1-NVFP4"
OUT = Path(os.environ.get("LONGCTX_OUT", "results/longctx"))

PAD_LINE = ("log[{i}] agent-turn checkpoint: lane probe ok, kv page flushed, "
            "queue depth nominal, tool result cached at /tmp/hermes/{i}.json\n")


def rand_nonce(n=48):
    return "".join(random.choices(string.ascii_letters + string.digits, k=n))


def build_prompt(n_lines: int, needle: str) -> str:
    nonce = rand_nonce()
    head = (f"# COLD-RUN NONCE (ignore): {nonce}\n"
            "You are retrieving a secret token from a long Hermes agent log.\n"
            "Ignore the padding. When asked, reply with ONLY the secret token string.\n\n")
    body = [PAD_LINE.format(i=i) for i in range(n_lines)]
    body.insert(n_lines // 2, f"\n*** SECRET TOKEN START ***\n{needle}\n*** SECRET TOKEN END ***\n\n")
    return head + "".join(body) + "\nQuestion: What is the secret token? Reply with only the token.\n"


def sample_kv_usage() -> float | None:
    try:
        with urllib.request.urlopen(METRICS, timeout=5) as r:
            for line in r.read().decode().splitlines():
                if line.startswith("vllm:kv_cache_usage_perc") or line.startswith("vllm:gpu_cache_usage_perc"):
                    return float(line.rsplit(" ", 1)[1])
    except Exception:
        return None
    return None


def timed_stream(prompt: str, max_tokens: int = 64, kv_sample: dict | None = None) -> dict:
    body = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.0,
        "stream": True,
        "stream_options": {"include_usage": True},
        "chat_template_kwargs": {"enable_thinking": False},
    }
    req = urllib.request.Request(f"{BASE}/chat/completions", data=json.dumps(body).encode(),
                                 method="POST", headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    t_first = t_last = None
    usage: dict = {}
    text: list[str] = []
    sampled = threading.Event()

    def sampler():
        # sample KV usage ~1s after first token (mid-decode)
        time.sleep(1.0)
        if kv_sample is not None:
            kv_sample["during"] = sample_kv_usage()
        sampled.set()

    try:
        with urllib.request.urlopen(req, timeout=3600) as resp:
            for raw in resp:
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                p = line[5:].strip()
                if p == "[DONE]":
                    break
                try:
                    obj = json.loads(p)
                except Exception:
                    continue
                now = time.perf_counter()
                if obj.get("usage"):
                    usage = obj["usage"]
                ch = obj.get("choices") or []
                if not ch:
                    continue
                delta = (ch[0].get("delta") or {}).get("content") or ""
                if delta:
                    if t_first is None:
                        t_first = now
                        threading.Thread(target=sampler, daemon=True).start()
                    t_last = now
                    text.append(delta)
        t1 = time.perf_counter()
    except urllib.error.HTTPError as e:
        try:
            msg = e.read().decode("utf-8", "replace")[:300]
        except Exception:
            msg = str(e)
        return {"ok": False, "http": e.code, "error": msg}
    except Exception as e:
        return {"ok": False, "error": str(e)}

    comp = usage.get("completion_tokens") or len(text)
    ttft = (t_first - t0) if t_first else None
    decode = round((comp - 1) / (t_last - t_first), 2) if (t_first and t_last and t_last > t_first and comp >= 2) else None
    return {
        "ok": True,
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": comp,
        "ttft_s": round(ttft, 3) if ttft else None,
        "decode_tok_s": decode,
        "total_wall_s": round(t1 - t0, 3),
        "response": "".join(text).strip()[:120],
    }


def cold_needle_run(n_lines: int, tag: str) -> dict:
    needle = f"HERMES-COLD-{tag}-{rand_nonce(8)}"
    prompt = build_prompt(n_lines, needle)
    kv = {}
    r = timed_stream(prompt, max_tokens=64, kv_sample=kv)
    r.update({"tag": tag, "n_lines": n_lines, "needle": needle,
              "needle_found": (needle in (r.get("response") or "")),
              "kv_usage_during": kv.get("during")})
    print(json.dumps({k: r.get(k) for k in ("tag", "ok", "http", "prompt_tokens", "ttft_s",
          "decode_tok_s", "total_wall_s", "needle_found", "kv_usage_during", "error")}), flush=True)
    return r


def fit_lines_for(target_tokens: int, ratio_hint: float) -> int:
    return max(10, int(target_tokens / ratio_hint))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    results = {"started_at": datetime.now(timezone.utc).isoformat(), "base": BASE,
               "method": "cold-prefill via unique first-line nonce (defeats prefix cache from position 0)",
               "runs": []}

    # calibrate tokens-per-line cheaply (~10K tokens, cold, max_tokens=1)
    cal = cold_needle_run(500, "CAL")
    tokens_per_line = (cal.get("prompt_tokens") or 25000) / 500.0
    results["tokens_per_line"] = round(tokens_per_line, 3)
    print(f"tokens_per_line={tokens_per_line:.2f}", flush=True)

    # ~100K cold x2
    n100 = fit_lines_for(100_000, tokens_per_line)
    for i in range(2):
        results["runs"].append(cold_needle_run(n100, f"100K-r{i}"))

    # ~200K cold x2 (may 400; then binary-search honest ceiling)
    n200 = fit_lines_for(200_000, tokens_per_line)
    r200 = cold_needle_run(n200, "200K-r0")
    results["runs"].append(r200)
    if r200.get("ok"):
        results["runs"].append(cold_needle_run(n200, "200K-r1"))
    else:
        lo, hi = n100, n200
        best = None
        for it in range(7):
            mid = (lo + hi) // 2
            r = cold_needle_run(mid, f"SEARCH-{it}")
            results["runs"].append(r)
            if r.get("ok"):
                best = r
                lo = mid
            else:
                hi = mid
            if hi - lo < 100:
                break
        results["honest_ceiling_prompt_tokens"] = best.get("prompt_tokens") if best else None

    # concurrency: 2 x ~100K cold simultaneous
    print("[concurrent 2x100K cold]", flush=True)
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=2) as ex:
        futs = [ex.submit(cold_needle_run, n100, f"CONC-{i}") for i in range(2)]
        conc = [f.result() for f in futs]
    wall = round(time.perf_counter() - t0, 3)
    agg = sum(c.get("completion_tokens") or 0 for c in conc if c.get("ok"))
    results["concurrent_2x100k"] = {"wall_s": wall, "streams": conc,
                                    "aggregate_completion_tokens": agg,
                                    "aggregate_tok_s_e2e": round(agg / wall, 2) if wall else None}

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    p = OUT / f"longctx_cold_{stamp}.json"
    p.write_text(json.dumps(results, indent=2), encoding="utf-8")
    (OUT / "LONGCTX_COLD_LATEST.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print("WROTE", p, flush=True)


if __name__ == "__main__":
    main()
