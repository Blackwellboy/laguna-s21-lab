#!/usr/bin/env python3
"""Arm B — single-shot generation shape (the shape the community says Qwen wins).

Cells (3 runs each, model-default sampling passed via LANE_SAMPLING):
  tetris_html : "write a complete working game one-shot" Tetris-class cell.
                Scored: HTML present, <canvas>, JS parses (node --check), feature
                checklist (rotate/clear/score/gameover/keydown), length.
  snake_py    : one-shot python snake (curses). Scored: py_compile + feature checklist.
  cli_todo_py : one-shot argparse todo CLI with JSON persistence. Scored: py_compile
                + run smoke (add/list roundtrip in tmpdir).
Also records decode tok/s per generation (stream).

Env: LANE_BASE, LANE_MODEL, LANE_LABEL, LANE_CTK, LANE_SAMPLING, ARM_RUNS, ARM_OUT.
"""
import json, os, re, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path

BASE = os.environ["LANE_BASE"]; MODEL = os.environ["LANE_MODEL"]
CTK = json.loads(os.environ["LANE_CTK"]) if os.environ.get("LANE_CTK") else None
SAMP = json.loads(os.environ.get("LANE_SAMPLING", "{}"))
RUNS = int(os.environ.get("ARM_RUNS", "3"))
OUT = Path(os.environ.get("ARM_OUT", "arm_b_results.json"))
ARTDIR = Path(os.environ.get("ARM_ARTDIR", "arm_b_artifacts")); ARTDIR.mkdir(exist_ok=True)

def stream_gen(prompt, max_tokens=6000):
    body = {"model": MODEL, "messages": [{"role":"user","content":prompt}],
            "max_tokens": max_tokens, "stream": True,
            "stream_options": {"include_usage": True}, **SAMP}
    if CTK: body["chat_template_kwargs"] = CTK
    req = urllib.request.Request(f"{BASE}/chat/completions", data=json.dumps(body).encode(),
        headers={"Content-Type":"application/json","Authorization":"Bearer dummy"})
    t0 = time.perf_counter(); t_first = t_last = None; parts = []; usage = {}
    with urllib.request.urlopen(req, timeout=1800) as resp:
        for raw in resp:
            line = raw.decode("utf-8","replace").strip()
            if not line.startswith("data:"): continue
            p = line[5:].strip()
            if p == "[DONE]": break
            try: obj = json.loads(p)
            except Exception: continue
            now = time.perf_counter()
            if obj.get("usage"): usage = obj["usage"]
            ch = obj.get("choices") or []
            if not ch: continue
            d = (ch[0].get("delta") or {}).get("content") or ""
            if d:
                if t_first is None: t_first = now
                t_last = now; parts.append(d)
    t1 = time.perf_counter()
    text = "".join(parts)
    comp = usage.get("completion_tokens") or max(1, len(text.split()))
    decode = (comp-1)/(t_last-t_first) if (t_first and t_last and t_last > t_first and comp >= 2) else None
    return text, {"completion_tokens": comp, "total_s": round(t1-t0,1),
                  "decode_tok_s": round(decode,2) if decode else None,
                  "finish_len_hit": comp >= max_tokens - 8}

def extract_block(text, lang_hints):
    blocks = re.findall(r"```[a-zA-Z]*\n([\s\S]*?)```", text)
    if blocks:
        return max(blocks, key=len)
    return text  # raw output (asked for no-markdown variants too)

def score_tetris(text):
    code = extract_block(text, ["html"])
    s = {"has_html": "<html" in code.lower() or "<!doctype" in code.lower(),
         "has_canvas": "<canvas" in code.lower(),
         "features": sum(k in code.lower() for k in ["rotate", "clear", "score", "keydown", "gameover" ]
                         ) + sum(k in code.lower() for k in ["arrowleft", "arrowdown"]) }
    js = re.findall(r"<script[^>]*>([\s\S]*?)</script>", code, re.I)
    s["js_parses"] = None
    if js:
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
            f.write(max(js, key=len)); p = f.name
        r = subprocess.run(["node", "--check", p], capture_output=True)
        s["js_parses"] = (r.returncode == 0)
        os.unlink(p)
    s["pass"] = bool(s["has_html"] and s["has_canvas"] and s["js_parses"] and s["features"] >= 4)
    return s, code

def score_python(text, smoke=None):
    code = extract_block(text, ["python"])
    s = {}
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(code); p = f.name
    r = subprocess.run([sys.executable, "-m", "py_compile", p], capture_output=True)
    s["compiles"] = (r.returncode == 0)
    s["smoke"] = None
    if smoke and s["compiles"]:
        s["smoke"] = smoke(p)
    s["pass"] = bool(s["compiles"] and (s["smoke"] is not False))
    os.unlink(p)
    return s, code

def todo_smoke(path):
    try:
        with tempfile.TemporaryDirectory() as d:
            env = dict(os.environ, HOME=d)
            a = subprocess.run([sys.executable, path, "add", "buy milk"], capture_output=True, timeout=20, env=env, cwd=d)
            l = subprocess.run([sys.executable, path, "list"], capture_output=True, timeout=20, env=env, cwd=d)
            return a.returncode == 0 and l.returncode == 0 and b"milk" in l.stdout
    except Exception:
        return False

CELLS = [
    {"id": "tetris_html", "scorer": "tetris", "max_tokens": 7000, "prompt":
     "Write a complete, working Tetris game as a single self-contained HTML file "
     "(inline CSS+JS, no external assets). Requirements: canvas rendering, all 7 "
     "tetrominoes, rotation, line clearing, scoring, increasing speed, keyboard "
     "controls (arrows), game over screen with restart. Output ONLY the HTML file."},
    {"id": "snake_py", "scorer": "python", "max_tokens": 4000, "prompt":
     "Write a complete, working terminal snake game in Python using curses, single "
     "file, no external deps. Arrow keys, food, growing snake, score, wall+self "
     "collision game over, q to quit. Output ONLY python code, no markdown fences if possible."},
    {"id": "cli_todo_py", "scorer": "todo", "max_tokens": 3000, "prompt":
     "Write a complete single-file Python CLI todo app: `todo.py add \"text\"`, "
     "`todo.py list`, `todo.py done N`, persisting to ~/.todo.json (create if "
     "missing). argparse, no external deps. Output ONLY python code."},
]

rows = []
for run in range(RUNS):
    for cell in CELLS:
        rec = {"run": run, "id": cell["id"], "error": None}
        try:
            text, speed = stream_gen(cell["prompt"], cell["max_tokens"])
            rec.update(speed)
            if cell["scorer"] == "tetris":
                s, code = score_tetris(text)
            elif cell["scorer"] == "python":
                s, code = score_python(text)
            else:
                s, code = score_python(text, smoke=todo_smoke)
            rec["score"] = s
            art = ARTDIR / f"{cell['id']}_run{run}{'.html' if cell['scorer']=='tetris' else '.py'}"
            art.write_text(code)
            rec["artifact"] = str(art)
        except Exception as e:
            rec["error"] = str(e)[:300]; rec["score"] = {"pass": False}
        print(f"run{run} {cell['id']:12s} pass={rec['score'].get('pass')} decode={rec.get('decode_tok_s')} err={rec['error']}", flush=True)
        rows.append(rec)

passes = sum(1 for r in rows if r["score"].get("pass"))
summary = {"label": os.environ.get("LANE_LABEL"), "model": MODEL, "sampling": SAMP, "ctk": CTK,
           "runs": RUNS, "cells": [c["id"] for c in CELLS], "passes": passes, "total": len(rows),
           "rows": rows}
OUT.write_text(json.dumps(summary, indent=2))
print(json.dumps({"label": summary["label"], "passes": passes, "total": len(rows)}))
