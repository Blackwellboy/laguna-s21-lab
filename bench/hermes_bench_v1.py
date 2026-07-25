#!/usr/bin/env python3
"""Hermes Bench v1 — independent Laguna protocol (NOT llama-benchy).

Design principles:
- Prompt shapes from Hermes agent traffic: tool-call, code refactor, JSON plan, prose
- Depths: 1K / 3K / 6K / 24K / 64K (not r0b0tlab 2/4/8/16K ladder)
- Gen lengths: 96 / 384 / 1024
- Concurrency: c=1 and c=4 (where depth allows)
- thinking off, temp 0, 3 runs, cache-bust nonces
- decode = (completion_tokens-1)/(t_last-t_first)
- non-stream e2e secondary
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE = os.environ.get("HERMES_BENCH_BASE", "http://localhost:8000/v1")
MODEL = os.environ.get("HERMES_BENCH_MODEL", "poolside/Laguna-S-2.1-NVFP4")
OUT = Path(os.environ.get("HERMES_BENCH_OUT", "results/bench"))
PROFILE_LABEL = os.environ.get("HERMES_BENCH_PROFILE", "unknown")

# Hermes-shaped seed corpora (our wording, not calibrated filler)
SEED_TOOL = """You are a coding agent with tools. Plan tool calls only as JSON.
Available tools: read_file(path), run_tests(cmd), apply_patch(diff), git_status().
User request: the flaky test test_auth_refresh fails intermittently after token expiry.
Diagnose, propose minimal patch, and list the exact tool sequence you would execute.
"""

SEED_CODE = """Refactor this module for clarity and O(n) where possible.
Keep public API stable. Add type hints and a brief module docstring.

```python
def merge(intervals):
    if not intervals: return []
    intervals = sorted(intervals)
    out = [intervals[0]]
    for s,e in intervals[1:]:
        if s <= out[-1][1]:
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append([s,e])
    return out

def topo(graph):
    from collections import deque, defaultdict
    indeg=defaultdict(int)
    for u,vs in graph.items():
        for v in vs: indeg[v]+=1
        indeg.setdefault(u,0)
    q=deque([u for u in indeg if indeg[u]==0])
    res=[]
    while q:
        u=q.popleft(); res.append(u)
        for v in graph.get(u,[]):
            indeg[v]-=1
            if indeg[v]==0: q.append(v)
    if len(res)!=len(indeg): raise ValueError('cycle')
    return res
```
Return only the refactored Python (no markdown fences).
"""

SEED_JSON = """Produce a fleet routing plan as STRICT JSON (no markdown) with keys:
objective, lanes (array of {name, role, endpoint_hint, when_to_use}),
fallback_order, risk_notes (array of strings).
Context: MiniMax pair for premium chat, DSV4 for 1M context, Laguna on single Spark for agentic coding.
"""

SEED_PROSE = """Summarize for an operator diary: why DFlash speculative decoding can accelerate
code generation yet underperform free-form agent reasoning on unified-memory GPUs.
Be concrete about acceptance rate, draft length, and when to disable speculation.
Write continuous prose (no bullet lists).
"""

FILLER_BLOCK = (
    "# hermes-context-pad session={sid} block={i}\n"
    "# Keep this as background conversation history for an agent turn.\n"
    "def pad_{i}(x):\n"
    "    '''padding helper {i} — ignore content, preserve structure.'''\n"
    "    return x if x is not None else 0\n"
    "NOTES: agent saw file paths /tmp/app/src/auth.py, /tmp/app/tests/test_auth.py\n"
)


def http_json(method: str, url: str, body: dict | None = None, timeout: float = 900.0):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={"Content-Type": "application/json", "Authorization": "Bearer dummy"},
    )
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            return r.status, json.loads(raw.decode()), time.perf_counter() - t0
    except urllib.error.HTTPError as e:
        try:
            err = e.read().decode("utf-8", "replace")
        except Exception:
            err = str(e)
        return e.code, {"error": err}, time.perf_counter() - t0
    except Exception as e:
        return 0, {"error": str(e)}, time.perf_counter() - t0


def build_prompt(category: str, target_tokens: int, nonce: str) -> str:
    seeds = {
        "tool": SEED_TOOL,
        "code": SEED_CODE,
        "json": SEED_JSON,
        "prose": SEED_PROSE,
    }
    base = seeds[category] + f"\n\n# nonce {nonce}\n"
    # grow with structured filler until approx target (probe later via usage)
    i = 0
    # rough: code-ish ~0.3 tokens/char
    while int(len(base) / 3.3) < target_tokens and i < 5000:
        base += FILLER_BLOCK.format(sid=nonce[:8], i=i)
        i += 1
    return base


def stream_chat(prompt: str, max_tokens: int) -> dict[str, Any]:
    body = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.0,
        "top_p": 1.0,
        "top_k": 20,
        "stream": True,
        "stream_options": {"include_usage": True},
        "chat_template_kwargs": {"enable_thinking": False},
    }
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{BASE}/chat/completions", data=data, method="POST",
        headers={"Content-Type": "application/json", "Authorization": "Bearer dummy"},
    )
    t0 = time.perf_counter()
    t_first = t_last = None
    usage: dict = {}
    text: list[str] = []
    try:
        with urllib.request.urlopen(req, timeout=1200) as resp:
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
                    t_last = now
                    text.append(delta)
        t1 = time.perf_counter()
    except Exception as e:
        return {"ok": False, "error": str(e)}

    comp = usage.get("completion_tokens") or max(1, len("".join(text).split()))
    prompt_toks = usage.get("prompt_tokens")
    ttft = (t_first - t0) if t_first else (t1 - t0)
    if t_first and t_last and t_last > t_first and comp >= 2:
        decode = (comp - 1) / (t_last - t_first)
    else:
        decode = comp / max(1e-6, (t1 - t0) - ttft)
    return {
        "ok": True,
        "method": "stream",
        "completion_tokens": comp,
        "prompt_tokens": prompt_toks,
        "ttft_s": round(ttft, 4),
        "ttft_ms": round(ttft * 1000, 2),
        "total_s": round(t1 - t0, 4),
        "decode_tok_s": round(decode, 2),
        "e2e_tok_s": round(comp / max(1e-6, t1 - t0), 2),
        "preview": "".join(text)[:160].replace("\n", " "),
    }


def nonstream_chat(prompt: str, max_tokens: int) -> dict[str, Any]:
    body = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.0,
        "top_p": 1.0,
        "top_k": 20,
        "stream": False,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    code, resp, dt = http_json("POST", f"{BASE}/chat/completions", body, timeout=1200)
    if code != 200:
        return {"ok": False, "error": resp, "http": code}
    usage = resp.get("usage") or {}
    msg = ((resp.get("choices") or [{}])[0].get("message") or {})
    content = msg.get("content") or ""
    if isinstance(content, list):
        content = "".join((p.get("text") if isinstance(p, dict) else str(p)) or "" for p in content)
    comp = usage.get("completion_tokens") or max(1, len(str(content).split()))
    return {
        "ok": True,
        "method": "nonstream",
        "http": code,
        "completion_tokens": comp,
        "prompt_tokens": usage.get("prompt_tokens"),
        "total_s": round(dt, 4),
        "e2e_tok_s": round(comp / max(1e-6, dt), 2),
        "preview": str(content)[:160].replace("\n", " "),
    }


def calibrate_prompt(category: str, target: int) -> str:
    """Binary-search-ish growth using real tokenizer via API."""
    nonce = f"cal-{category}-{target}-{time.time()}"
    prompt = build_prompt(category, target, nonce)
    # one probe
    r = stream_chat(prompt, max_tokens=4)
    if not r.get("ok"):
        return prompt
    got = r.get("prompt_tokens") or target
    if got < target * 0.85:
        # grow
        extra = int((target - got) * 4)
        prompt += ("# pad\n" + "x" * max(extra, 100) + "\n") * max(1, (target - got) // 50)
    elif got > target * 1.15:
        # shrink by truncation
        ratio = target / got
        prompt = prompt[: int(len(prompt) * ratio)]
    return prompt


def run_matrix(depths: list[int], gens: list[int], categories: list[str], runs: int, concurrency: int) -> dict:
    rows = []
    # warm
    print("[warm]", flush=True)
    stream_chat("Reply OK only.", 8)

    for depth in depths:
        for cat in categories:
            print(f"[calibrate] {cat} depth~{depth}", flush=True)
            base_prompt = calibrate_prompt(cat, depth)
            # probe actual tokens
            probe = stream_chat(base_prompt + f"\n# probe {time.time()}", 4)
            actual_depth = probe.get("prompt_tokens") if probe.get("ok") else None
            print(f"  actual_prompt_tokens={actual_depth}", flush=True)
            for gen in gens:
                # skip absurd combos (64k * 1024 * c4 too long for audit window)
                if depth >= 24000 and gen >= 1024 and concurrency > 1:
                    continue
                if depth >= 64000 and gen > 96:
                    gens_here = [96]
                else:
                    gens_here = [gen]
                for g in gens_here:
                    for run_i in range(runs):
                        nonce = f"{PROFILE_LABEL}-{cat}-d{depth}-g{g}-r{run_i}-{time.time()}"
                        prompt = base_prompt + f"\n# cachebust {nonce}\n"

                        def one(idx=0, p=prompt, gg=g):
                            return stream_chat(p + f" worker={idx}", gg)

                        if concurrency <= 1:
                            print(f"[run] {cat} d~{depth} g={g} r={run_i} c=1", flush=True)
                            r = one()
                            r.update({
                                "category": cat, "target_depth": depth, "actual_depth": actual_depth,
                                "gen": g, "run": run_i, "concurrency": 1, "profile": PROFILE_LABEL,
                            })
                            rows.append(r)
                            print(f"  decode={r.get('decode_tok_s')} n={r.get('completion_tokens')} ttft={r.get('ttft_ms')}", flush=True)
                            # secondary nonstream only for small cells
                            if depth <= 3000 and g <= 96 and run_i == 0:
                                ns = nonstream_chat(prompt, g)
                                ns.update({
                                    "category": cat, "target_depth": depth, "actual_depth": actual_depth,
                                    "gen": g, "run": run_i, "concurrency": 1, "profile": PROFILE_LABEL,
                                    "paired_with": "stream",
                                })
                                rows.append(ns)
                        else:
                            print(f"[run] {cat} d~{depth} g={g} r={run_i} c={concurrency}", flush=True)
                            t0 = time.perf_counter()
                            with ThreadPoolExecutor(max_workers=concurrency) as ex:
                                futs = [ex.submit(one, i) for i in range(concurrency)]
                                parts = [f.result() for f in as_completed(futs)]
                            wall = time.perf_counter() - t0
                            okp = [p for p in parts if p.get("ok")]
                            total_tok = sum(p.get("completion_tokens") or 0 for p in okp)
                            row = {
                                "ok": len(okp) == concurrency,
                                "method": "stream_concurrent",
                                "category": cat, "target_depth": depth, "actual_depth": actual_depth,
                                "gen": g, "run": run_i, "concurrency": concurrency, "profile": PROFILE_LABEL,
                                "wall_s": round(wall, 3),
                                "aggregate_tok_s": round(total_tok / max(1e-6, wall), 2),
                                "median_decode_tok_s": round(statistics.median([p["decode_tok_s"] for p in okp]), 2) if okp else None,
                                "workers": parts,
                            }
                            rows.append(row)
                            print(f"  agg={row['aggregate_tok_s']} med_dec={row['median_decode_tok_s']}", flush=True)
    return summarize(rows)


def summarize(rows: list[dict]) -> dict:
    by_cat: dict[str, list[float]] = {}
    by_depth: dict[str, list[float]] = {}
    stream_singles = [r for r in rows if r.get("ok") and r.get("method") == "stream" and r.get("concurrency") == 1]
    for r in stream_singles:
        by_cat.setdefault(r["category"], []).append(r["decode_tok_s"])
        by_depth.setdefault(str(r["target_depth"]), []).append(r["decode_tok_s"])
    prose = by_cat.get("prose", [])
    code = by_cat.get("code", [])
    return {
        "protocol": "hermes_bench_v1",
        "profile": PROFILE_LABEL,
        "base": BASE,
        "model": MODEL,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "n_rows": len(rows),
        "n_stream_c1": len(stream_singles),
        "median_decode_by_category": {k: round(statistics.median(v), 2) for k, v in by_cat.items() if v},
        "mean_decode_by_category": {k: round(statistics.mean(v), 2) for k, v in by_cat.items() if v},
        "median_decode_by_depth": {k: round(statistics.median(v), 2) for k, v in by_depth.items() if v},
        "prose_floor_median": round(statistics.median(prose), 2) if prose else None,
        "code_median": round(statistics.median(code), 2) if code else None,
        "overall_median_decode_c1": round(statistics.median([r["decode_tok_s"] for r in stream_singles]), 2) if stream_singles else None,
        "overall_mean_decode_c1": round(statistics.mean([r["decode_tok_s"] for r in stream_singles]), 2) if stream_singles else None,
        "rows": rows,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="Reduced matrix for faster A/B")
    ap.add_argument("--full", action="store_true")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    if args.quick:
        depths = [1000, 3000, 6000]
        gens = [96, 384]
        categories = ["tool", "code", "json", "prose"]
        runs = 3
        conc_list = [1, 4]
    else:
        # full hermes v1
        depths = [1000, 3000, 6000, 24000, 64000]
        gens = [96, 384, 1024]
        categories = ["tool", "code", "json", "prose"]
        runs = 3
        conc_list = [1, 4]

    all_rows = []
    # run c=1 matrix
    m1 = run_matrix(depths, gens, categories, runs, concurrency=1)
    all_rows.extend(m1["rows"])
    # run c=4 only on shallow depths
    shallow = [d for d in depths if d <= 6000]
    if 4 in conc_list:
        m4 = run_matrix(shallow, [96, 384], categories, runs=2, concurrency=4)
        all_rows.extend(m4["rows"])

    summary = summarize(all_rows)
    # merge category stats already in summary
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = OUT / f"hermes_bench_v1_{PROFILE_LABEL}_{stamp}.json"
    latest = OUT / f"HERMES_BENCH_V1_{PROFILE_LABEL}_LATEST.json"
    path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    latest.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("WROTE", path, flush=True)
    print(json.dumps({
        "profile": PROFILE_LABEL,
        "median_by_cat": summary["median_decode_by_category"],
        "prose_floor": summary["prose_floor_median"],
        "code_median": summary["code_median"],
        "overall_median": summary["overall_median_decode_c1"],
        "overall_mean": summary["overall_mean_decode_c1"],
    }, indent=2), flush=True)


if __name__ == "__main__":
    main()
