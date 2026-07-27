#!/usr/bin/env python3
"""Laguna 3.25bpw EXL3-hybrid context-mass sweep — 2026-07-29 (fable).

THE COMMITTED FOLLOW-UP to the Laguna gate study: single-turn C7 fires 60-72%,
the 12h soak under agent prompts fired ~0.1% over 3,099 turns. This sweep asks
whether accumulated conversation depth and/or context mass closes the gate.

Lane: spark-node-b :8101, laguna-s-2.1-tr3-hybrid (0xSero 3.25bpw EXL3-hybrid,
own vLLM container, poolside_v1 parsers). KNOWN LANE BUG: the misconfigured
reasoning parser can leak a stray leading '</think>' into content — every
content string is passed through clean_content() before any analysis, and
shim trigger incidence is logged.

REUSED BYTE-IDENTICAL (imported from the 2026-07-28 Qwen driver module, which
itself carried them verbatim from the Laguna gate-study driver):
  - C7 system prompt (incl. PROVENANCE_CLAUSE)
  - the 4 task-type prompts (transfer check)
Sampling = Laguna model-card defaults (temp 0.7 / top_p 0.95 / top_k 20),
matching the original Laguna gate study (NOT the Qwen study's 1.0).

DESIGN
  Phase 0  control pair: 4 tasks x enable_thinking {true,false} — two-sided
           detection verification (reasoning non-empty iff thinking on).
  Phase 1  transfer check: C7 single-turn, 4 tasks x 5 = 20 samples.
           GATE: firing in [50%, 75%] -> sweep proceeds; else STOP file.
  Phase 2  sweep: depth {1,5,10,20,40} x target mass {2K, 8K, 32K} tokens.
           History = realistic agent-shaped exchanges under the C7 system
           prompt, content drawn from the 12h soak driver's task corpus
           (same corpus dir), steered per-turn toward the target mass.
           depth<=10 cells: 2 independent histories x 5 probes;
           depth 20/40 cells: 1 history x 10 probes (runtime bound; scoped).
           Probe = fresh reasoning-warranted task (the gate-study 'reasoning'
           task template), nonce-prefixed, appended as final user turn,
           ceiling 4096. Per-probe: fired y/n, reasoning/completion tokens,
           cap-hit, latency, actual prompt_tokens at probe time.

HISTORY MECHANICS (documented deviations from 'pure' replication):
  - assistant history turns are generated live with thinking ON (agent-real);
    per OpenAI-API convention only cleaned content enters history. If content
    comes back empty (all-thinking-to-ceiling), ONE retry with thinking off
    supplies the transcript text; fallback count logged per cell.
  - low-mass/high-depth cells get short ops-style follow-ups; high-mass cells
    get corpus-doc chunks. Actual prompt_tokens at probe time is the measured
    mass — cells that physically can't reach their target (e.g. depth 40 at
    2K) are reported at their ACTUAL mass, never forced.
  - raw corpus text is NOT logged in JSONL (ops content, sanitizer): history
    turns log doc source name, char count, sha1 prefix only.
"""
import hashlib, importlib.util, json, os, random, secrets, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

ORIG = "<UPSTREAM_DRIVER>/qwen_gate_study_driver.py"
spec = importlib.util.spec_from_file_location("qwen_base", ORIG)
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
C7 = base.C7
TASKS = base.TASKS

ENDPOINT = "http://localhost:8101/v1"
MODEL = "laguna-s-2.1-tr3-hybrid"
OUT = Path(os.path.expanduser("results/context_mass_sweep_20260729"))
LOGS = OUT / "logs"
LOGS.mkdir(parents=True, exist_ok=True)
CORPUS = Path(os.path.expanduser("corpus/"))

TEMPERATURE, TOP_P, TOP_K = 0.7, 0.95, 20   # Laguna model-card defaults
PROBE_CEILING = 4096
DEPTHS = [1, 5, 10, 20, 40]
MASSES = [2000, 8000, 32000]
CELL_CONC = int(os.environ.get("CELL_CONC", "3"))
PROBE_CONC = int(os.environ.get("PROBE_CONC", "4"))
_loglock = Lock()

rng = random.Random(20260729)


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def log(path, obj):
    obj = dict(obj); obj.setdefault("ts", utcnow())
    with _loglock:
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def note(msg):
    print(f"[{utcnow()}] {msg}", flush=True)


def clean_content(content):
    """Strip the lane's known stray leading '</think>' leak; report trigger."""
    stripped = content.lstrip()
    if stripped.startswith("</think>"):
        return stripped[len("</think>"):].lstrip(), True
    return content, False


def chat(messages, max_tokens, thinking=True):
    body = {
        "model": MODEL, "messages": messages, "max_tokens": max_tokens,
        "temperature": TEMPERATURE, "top_p": TOP_P, "top_k": TOP_K,
        "chat_template_kwargs": {"enable_thinking": thinking},
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


def measure(resp):
    ch = (resp.get("choices") or [{}])[0]
    msg = ch.get("message") or {}
    raw_content = msg.get("content") or ""
    content, shim_hit = clean_content(raw_content)
    rc = msg.get("reasoning_content") or msg.get("reasoning") or ""
    usage = resp.get("usage") or {}
    return {
        "thinking_fired": bool(rc),
        "reasoning_chars": len(rc),
        "reasoning_tokens_est": max(1, len(rc) // 4) if rc else 0,
        "content_chars": len(content),
        "shim_stripped_leading_close_think": shim_hit,
        "completion_tokens": usage.get("completion_tokens"),
        "prompt_tokens": usage.get("prompt_tokens"),
        "finish_reason": ch.get("finish_reason"),
        "cap_hit": ch.get("finish_reason") == "length",
        "content_preview": content[:200],
        "reasoning_preview": rc[:200],
        "_content": content,
    }


# ---------------- corpus ----------------

def load_corpus():
    docs = sorted(CORPUS.glob("doc_*.txt"))
    deep = sorted(CORPUS.glob("deep_context_pack_*.txt"))
    diff = CORPUS / "code_diff_sample.patch"
    return docs, deep, diff


SHORT_FOLLOWUPS = [
    "Proceed to the next step. Keep it brief.",
    "Acknowledged. What is the single highest risk here?",
    "Tighten your last answer to two sentences.",
    "OK. Next: state one concrete acceptance check.",
    "Noted. Anything you would roll back? One line.",
    "Continue. Flag any assumption you made, briefly.",
]

STRUCTURED_FOLLOWUPS = [
    "Produce a structured JSON plan with keys: goal, steps[5], acceptance_criteria[3], rollback. No markdown fences.",
    "Critique your previous answer for factual risk and tighten it to half length.",
    "Simulate a tool-call round: propose a tool named probe_service with args {host, port} for a health check, then describe the expected result if the tool returned healthy.",
    "List the top 3 open questions from this session so far, one line each.",
]


def doc_chunk_task(docs, diff, budget_chars):
    """A soak-style doc task sized to ~budget_chars of pasted content."""
    if diff.exists() and rng.random() < 0.25:
        body = diff.read_text(encoding="utf-8", errors="replace")[:budget_chars]
        return (f"Code review this real diff. List bugs, missing tests, and risk.\n\n{body}",
                {"src": diff.name, "chars": len(body)})
    d = rng.choice(docs)
    body = d.read_text(encoding="utf-8", errors="replace")[:budget_chars]
    return (f"Summarize section findings from {d.name} as 5 bullets then 3 risks.\n\n{body}",
            {"src": d.name, "chars": len(body)})


def deep_chunk_task(deep, budget_chars):
    pack = rng.choice(deep)
    body = pack.read_text(encoding="utf-8", errors="replace")
    start = rng.randrange(0, max(1, len(body) - budget_chars))
    body = body[start:start + budget_chars]
    return ("Ingest the following context pack excerpt. Do NOT dump it back. "
            "Acknowledge with: (1) size class, (2) top 3 themes, (3) one open question.\n\n" + body,
            {"src": pack.name, "chars": len(body), "offset": start})


def build_history(cell_id, depth, target_mass, docs, deep, diff, hist_log):
    """Build a depth-turn history under C7 steering toward target_mass tokens.
    Returns (messages, meta). Serial by nature (each turn depends on last)."""
    messages = [{"role": "system", "content": C7}]
    tokens_now = 0          # last observed prompt_tokens + completion_tokens
    fallbacks = 0
    for turn in range(depth):
        remaining_turns = depth - turn
        remaining_budget = max(0, target_mass - tokens_now)
        per_turn = remaining_budget / remaining_turns
        # split user/assistant ~60/40; floor keeps exchanges non-degenerate
        user_budget_chars = int(max(0, per_turn * 0.6) * 4)
        asst_budget_tok = int(max(24, min(700, per_turn * 0.4)))
        if user_budget_chars > 6000 and deep:
            prompt, src = deep_chunk_task(deep, user_budget_chars)
        elif user_budget_chars > 800 and docs:
            prompt, src = doc_chunk_task(docs, diff, user_budget_chars)
        elif per_turn > 120:
            prompt, src = rng.choice(STRUCTURED_FOLLOWUPS), {"src": "structured_followup"}
        else:
            prompt, src = rng.choice(SHORT_FOLLOWUPS), {"src": "short_followup"}
        nonce = secrets.token_hex(3)
        messages.append({"role": "user", "content": f"[h-{nonce}] {prompt}"})
        # thinking allowance on top of the content budget (reasoning does not
        # enter history; it just needs room so content isn't starved)
        status, resp, lat = chat(messages, asst_budget_tok + 1500, thinking=True)
        row = {"cell": cell_id, "phase": "history", "turn": turn,
               "http_status": status, "latency_s": round(lat, 3), **src}
        content = ""
        if status == 200:
            m = measure(resp)
            content = m.pop("_content")
            row.update({k: m[k] for k in
                        ("thinking_fired", "reasoning_tokens_est", "completion_tokens",
                         "prompt_tokens", "finish_reason", "cap_hit",
                         "shim_stripped_leading_close_think")})
            tokens_now = (m["prompt_tokens"] or 0) + (m["completion_tokens"] or 0)
        if not content.strip():
            status2, resp2, _ = chat(messages, asst_budget_tok + 50, thinking=False)
            if status2 == 200:
                m2 = measure(resp2)
                content = m2.pop("_content")
                tokens_now = (m2["prompt_tokens"] or 0) + (m2["completion_tokens"] or 0)
            fallbacks += 1
            row["thinking_off_fallback"] = True
        if not content.strip():
            content = "Acknowledged."
            row["hard_fallback_placeholder"] = True
        # sanitizer: log hash/len of user text, never the raw corpus text
        u = messages[-1]["content"]
        row["user_sha1_12"] = hashlib.sha1(u.encode()).hexdigest()[:12]
        row["user_chars"] = len(u)
        row["assistant_chars"] = len(content)
        row["tokens_now_est"] = tokens_now
        log(hist_log, row)
        messages.append({"role": "assistant", "content": content})
    return messages, {"fallbacks": fallbacks, "tokens_final_est": tokens_now}


PROBE_TASK = TASKS["reasoning"]   # byte-identical gate-study reasoning task


def run_probe(probe_log, cell_id, depth, mass, hist_idx, messages, idx):
    nonce = secrets.token_hex(4)
    msgs = messages + [{"role": "user", "content": f"[probe-{nonce}] {PROBE_TASK}"}]
    status, resp, lat = chat(msgs, PROBE_CEILING, thinking=True)
    row = {"phase": "probe", "cell": cell_id, "depth": depth,
           "target_mass": mass, "history_idx": hist_idx, "sample": idx,
           "nonce": nonce, "http_status": status, "latency_s": round(lat, 3)}
    if status == 200:
        m = measure(resp)
        m.pop("_content")
        row.update(m)
    else:
        row["error"] = resp.get("error", f"http_{status}")
    log(probe_log, row)
    return row


def transfer_check():
    ctl = LOGS / "control_pair.jsonl"
    ok_two_sided = True
    for thinking in (True, False):
        for t, p in TASKS.items():
            nonce = secrets.token_hex(4)
            status, resp, lat = chat(
                [{"role": "system", "content": C7},
                 {"role": "user", "content": f"[ctl-{nonce}] {p}"}],
                PROBE_CEILING, thinking=thinking)
            row = {"phase": "control", "thinking_kwarg": thinking, "task_type": t,
                   "http_status": status, "latency_s": round(lat, 3)}
            if status == 200:
                m = measure(resp); m.pop("_content"); row.update(m)
                if not thinking and m["reasoning_chars"] > 0:
                    ok_two_sided = False
            log(ctl, row)
            note(f"control think={thinking} {t}: reasoning_chars={row.get('reasoning_chars')}")
    tc = LOGS / "transfer_check.jsonl"
    jobs = [(t, i, p) for t, p in TASKS.items() for i in range(5)]
    def one(j):
        t, i, p = j
        nonce = secrets.token_hex(4)
        status, resp, lat = chat(
            [{"role": "system", "content": C7},
             {"role": "user", "content": f"[run-{nonce}] {p}"}],
            PROBE_CEILING, thinking=True)
        row = {"phase": "transfer_check", "condition": "C7", "task_type": t,
               "sample": i, "http_status": status, "latency_s": round(lat, 3)}
        if status == 200:
            m = measure(resp); m.pop("_content"); row.update(m)
        log(tc, row)
        return row
    with ThreadPoolExecutor(max_workers=PROBE_CONC) as ex:
        rows = list(ex.map(one, jobs))
    ok = [r for r in rows if r.get("http_status") == 200]
    fired = sum(1 for r in ok if r.get("thinking_fired"))
    rate = fired / len(ok) if ok else 0.0
    verdict = {"fired": fired, "total": len(ok), "rate": round(rate, 3),
               "two_sided_control_ok": ok_two_sided,
               "band": [0.50, 0.75],
               "in_band": 0.50 <= rate <= 0.75,
               "per_task": {t: sum(1 for r in ok if r.get("task_type") == t
                                   and r.get("thinking_fired")) for t in TASKS}}
    (OUT / "transfer_verdict.json").write_text(json.dumps(verdict, indent=1))
    note(f"TRANSFER CHECK: {fired}/{len(ok)} ({rate:.0%}) two_sided_ok={ok_two_sided} in_band={verdict['in_band']}")
    return verdict


def run_cell(cell, docs, deep, diff):
    depth, mass = cell
    cell_id = f"d{depth}_m{mass//1000}k"
    hist_log = LOGS / "history_turns.jsonl"
    probe_log = LOGS / "probe_turns.jsonl"
    n_hist = 2 if depth <= 10 else 1
    probes_per = 5 if n_hist == 2 else 10
    results = []
    for h in range(n_hist):
        t0 = time.time()
        messages, meta = build_history(cell_id, depth, mass, docs, deep, diff, hist_log)
        note(f"CELL {cell_id} hist{h}: built depth={depth} est_tokens={meta['tokens_final_est']} "
             f"fallbacks={meta['fallbacks']} in {round(time.time()-t0)}s")
        with ThreadPoolExecutor(max_workers=PROBE_CONC) as ex:
            rows = list(ex.map(
                lambda i: run_probe(probe_log, cell_id, depth, mass, h, messages, i),
                range(probes_per)))
        results.extend(rows)
    ok = [r for r in results if r.get("http_status") == 200]
    fired = sum(1 for r in ok if r.get("thinking_fired"))
    pt = [r.get("prompt_tokens") for r in ok if r.get("prompt_tokens")]
    note(f"CELL {cell_id}: fired {fired}/{len(ok)} actual_prompt_tokens="
         f"{min(pt) if pt else '?'}..{max(pt) if pt else '?'}")
    return cell_id, fired, len(ok)


def main():
    note(f"context-mass sweep start endpoint={ENDPOINT} model={MODEL}")
    docs, deep, diff = load_corpus()
    note(f"corpus: {len(docs)} docs, {len(deep)} deep packs, diff={diff.exists()}")
    if os.environ.get("SKIP_TRANSFER") != "1":
        v = transfer_check()
        if not v["in_band"] or not v["two_sided_control_ok"]:
            note("TRANSFER CHECK OUT OF BAND — STOPPING Study A per protocol")
            (OUT / "STOPPED_TRANSFER_DIVERGENCE").write_text(utcnow())
            sys.exit(3)
    cells = [(d, m) for d in DEPTHS for m in MASSES]
    # cheap cells first so early output accumulates; heavy 40-depth last
    cells.sort(key=lambda c: c[0] * max(1, c[1] // 1000))
    with ThreadPoolExecutor(max_workers=CELL_CONC) as ex:
        list(ex.map(lambda c: run_cell(c, docs, deep, diff), cells))
    note("context-mass sweep COMPLETE")


if __name__ == "__main__":
    main()
