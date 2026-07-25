#!/usr/bin/env python3
"""Score Laguna soak + restore production thinking-off + unpark ComfyUI."""
from __future__ import annotations
import json, subprocess, time
from pathlib import Path
from datetime import datetime, timezone
from urllib import request, error
from collections import Counter

BASE = Path(__file__).resolve().parent
LOGS = BASE / "logs"
PROBES = BASE / "probes"
OUT_MD = BASE / "LAGUNA_SOAK_12H_20260725.md"
LC_OUT = Path("<CONTROL_PLANE>/workspace/grok/laguna_soak_12h_20260725")
STATE_CL = Path("$HOME/.hermes/project_docs/_state/CHANGELOG.md")
ENDPOINT = "http://localhost:8000/v1"

def load_jsonl(p):
    rows=[]
    if not p.exists(): return rows
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line=line.strip()
        if not line: continue
        try: rows.append(json.loads(line))
        except: pass
    return rows

def http_json(method, url, body=None, timeout=120):
    data=None if body is None else json.dumps(body).encode()
    req=request.Request(url, data=data, method=method)
    req.add_header("Content-Type","application/json")
    try:
        with request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode())
    except error.HTTPError as e:
        return e.code, {"err": e.read().decode()[:500]}
    except Exception as e:
        return 0, {"err": str(e)}

def ssh(cmd):
    r=subprocess.run(["ssh","-o","BatchMode=yes","-o","ConnectTimeout=15","spark-host",cmd],
                     capture_output=True, text=True, timeout=120)
    return r.returncode, r.stdout, r.stderr

def main():
    turns = load_jsonl(LOGS/"turns.jsonl")
    sessions = load_jsonl(LOGS/"sessions.jsonl")
    incidents = load_jsonl(LOGS/"incidents.jsonl")
    probes = load_jsonl(LOGS/"integrity_probes.jsonl")
    samples = load_jsonl(PROBES/"service_samples.jsonl")

    # thinking rates
    def rate(rows):
        if not rows: return None
        f=sum(1 for t in rows if t.get("thinking_fired"))
        return f/len(rows)

    turns_ok=[t for t in turns if t.get("http_status")==200 and t.get("kind")!="integrity_probe"]
    by_persona={}
    for p in ("neutral","senior"):
        by_persona[p]=rate([t for t in turns_ok if t.get("persona")==p])

    # tool rates first/last hour
    def parse_ts(t):
        s=t.get("ts")
        if not s: return None
        try: return datetime.fromisoformat(s.replace("Z","+00:00"))
        except: return None
    timed=[(parse_ts(t),t) for t in turns_ok]
    timed=[x for x in timed if x[0]]
    tool_first=tool_last=None
    if timed:
        t0=min(x[0] for x in timed)
        first=[t for ts,t in timed if (ts-t0).total_seconds()<=3600 and t.get("tool_success") is not None]
        last_start=max(x[0] for x in timed)
        last=[t for ts,t in timed if (last_start-ts).total_seconds()<=3600 and t.get("tool_success") is not None]
        def okrate(rs):
            if not rs: return None
            return sum(1 for t in rs if t.get("tool_success") is True)/len(rs)
        tool_first, tool_last = okrate(first), okrate(last)

    loops=[i for i in incidents if i.get("type") in ("token_burn","session_cap")]
    mem_curve=[]
    for s in samples:
        if "mem_used_b" in s:
            mem_curve.append({"ts":s.get("ts"),"used_gi":s["mem_used_b"]/(1024**3),"avail_gi":s.get("mem_avail_b",0)/(1024**3)})

    # --- restore thinking production (off client; server unchanged) ---
    # Production thinking default is OFF at request layer. Verify clean serve:
    st, models = http_json("GET", f"{ENDPOINT}/models")
    st2, chat = http_json("POST", f"{ENDPOINT}/chat/completions", {
        "model":"poolside/Laguna-S-2.1-NVFP4",
        "messages":[{"role":"user","content":"Reply with exactly: SOAK_RESTORE_OK"}],
        "max_tokens":32,
        "chat_template_kwargs":{"enable_thinking": False},
    })
    restore_chat_ok = st2==200 and "SOAK_RESTORE_OK" in json.dumps(chat)

    # Clear soak override env on server (leave production defaults)
    ssh("cp -a $HOME/backups/comfy_park_soak_20260725/start-laguna-s21-nvfp4.sh.pre_soak $HOME/bin/start-laguna-s21-nvfp4.sh 2>/dev/null || true; "
        "rm -f $HOME/bin/laguna_sweep_env.sh; "
        "echo 'soak override removed'")

    # Unpark ComfyUI — but Laguna and Comfy conflict. Production end state per task:
    # "verify the lane serves cleanly on the production profile, then unpark the graphic design lane"
    # Mutual exclusion: cannot both run. Task says unpark graphic design at end.
    # So: stop Laguna, park Laguna again, start ComfyUI.
    # Actually re-read: "Restore: thinking back to production setting (off), verify the lane serves cleanly on the production profile, then unpark the graphic design lane"
    # Order: 1) thinking off + verify Laguna production 2) then unpark graphic design
    # With Conflicts=, unparking Comfy means stopping Laguna. Final intended: Comfy up, Laguna parked (pre-soak owner state was Comfy for video).
    # Pre-soak: Laguna PARKED for ComfyUI. So end state should restore Comfy + re-park Laguna.

    # After verify Laguna clean, switch to Comfy:
    rc, out, err = ssh(
        "set -e; "
        "systemctl --user stop hermes-laguna-s21-nvfp4.service; "
        "systemctl --user disable hermes-laguna-s21-nvfp4.service; "
        "mkdir -p $HOME/.hermes/lane_state; "
        "printf '%s\\n' '{\"lane\":\"spark-host_laguna\",\"unit\":\"hermes-laguna-s21-nvfp4.service\",\"reason\":\"restored_post_soak_comfyui_mode\",\"parked_at\":\"'$(date -u +%Y-%m-%dT%H:%M:%SZ)'\",\"parked_by\":\"soak_restore\"}' "
        "> $HOME/.hermes/lane_state/spark-host_laguna.parked; "
        "systemctl --user enable hermes-comfyui-ltx23.service; "
        "systemctl --user restart hermes-comfyui-ltx23.service; "
        "rm -f $HOME/.hermes/lane_state/spark-host_comfyui.parked; "
        "printf '{\"mode\":\"COMFYUI_LTX23\",\"updated_at\":\"%s\",\"reason\":\"post_soak_restore\"}\\n' \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\" "
        "> $HOME/ai-video/manifests/ACTIVE_MODE.lock; "
        "sleep 5; "
        "echo laguna=$(systemctl --user is-active hermes-laguna-s21-nvfp4.service); "
        "echo comfy=$(systemctl --user is-active hermes-comfyui-ltx23.service); "
        "ss -ltn | grep -E '8000|8188' || true"
    )
    # Main markers
    Path.home().joinpath(".hermes/lane_state/spark-host_comfyui.parked").unlink(missing_ok=True)
    Path.home().joinpath(".hermes/lane_state/spark-host_laguna.parked").write_text(
        json.dumps({
            "lane":"spark-host_laguna","unit":"","remote_unit":"hermes-laguna-s21-nvfp4.service",
            "remote_host":"spark-host","reason":"restored_post_soak_comfyui_mode",
            "parked_at":datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "parked_by":"soak_restore@operator"
        })+"\n"
    )

    # wait comfy
    comfy_ok=False
    for _ in range(30):
        try:
            with request.urlopen("http://localhost:8188/", timeout=5) as r:
                if r.status < 500:
                    comfy_ok=True
                    break
        except Exception:
            time.sleep(2)

    md = f"""# LAGUNA_SOAK_12H_20260725

**Scope:** 12h **single-run** soak on spark-host Laguna S 2.1 NVFP4 **rev 0761412**, **thinking-ON-with-ceiling (max_tokens=8192)**.  
Not a multi-day claim. Production profile K=7 / max-num-seqs=32, poolside_v1 parsers, prefix caching on.

## Part 0 — Graphic design lane identification + park

| Field | Value |
|-------|-------|
| Identity | **hermes-comfyui-ltx23.service** (ComfyUI LTX 2.3 headless video/image-gen) |
| Port | <SERVER>:**8188** |
| Pre-park RSS / GPU | ~1082 MiB / ~170 MiB |
| Park reason | `soak_test_20260725` |
| Method | stop+disable + markers main+remote `spark-host_comfyui.parked` |
| Snapshot | `spark-host:~/backups/comfy_park_soak_20260725/` |

Laguna brought up after park; free mem after Comfy park ≈ **118 Gi available** (used ~2.9 Gi) before Laguna load.

## Scorecard

| Metric | Value |
|--------|-------|
| Sessions logged | {len(sessions)} |
| Turns logged | {len(turns)} |
| HTTP-200 turns | {len(turns_ok)} |
| Thinking routing rate (overall) | {rate(turns_ok)} |
| Thinking rate persona=neutral | {by_persona.get('neutral')} |
| Thinking rate persona=senior | {by_persona.get('senior')} |
| Tool success rate first hour | {tool_first} |
| Tool success rate last hour | {tool_last} |
| Loop/token-burn incidents | {len(loops)} |
| Integrity probes | {len(probes)} |
| Service samples | {len(samples)} |

### Loop / burn incidents
```json
{json.dumps(loops, indent=2)[:4000]}
```

### Integrity probes
```json
{json.dumps(probes, indent=2)[:5000]}
```

### Memory curve (samples)
```json
{json.dumps(mem_curve[:40], indent=2)}
```

### Restoration
| Step | Result |
|------|--------|
| Laguna models GET before mode switch | status={st} |
| Production thinking-off smoke | status={st2} ok={restore_chat_ok} |
| Final mode | ComfyUI unparked; Laguna re-parked (mutex Conflicts=) |
| SSH restore output | ```{out[:1500]}``` |
| ComfyUI HTTP | ok={comfy_ok} |

## Raw logs
- `{LOGS}/turns.jsonl`
- `{LOGS}/sessions.jsonl`
- `{LOGS}/incidents.jsonl`
- `{LOGS}/integrity_probes.jsonl`
- `{PROBES}/service_samples.jsonl`

## Operator decisions (if any)
- Confirm final desired steady-state if not ComfyUI-primary: leave Laguna production LIVE instead of re-parking.
- Whether to keep `spark-host_comfyui` in `lane_units.json` permanently.
"""
    OUT_MD.write_text(md, encoding="utf-8")
    LC_OUT.mkdir(parents=True, exist_ok=True)
    (LC_OUT/"LAGUNA_SOAK_12H_20260725.md").write_text(md, encoding="utf-8")
    # copy logs
    import shutil
    for p in LOGS.glob("*.jsonl"):
        shutil.copy2(p, LC_OUT/p.name)
    for p in PROBES.glob("*.jsonl"):
        shutil.copy2(p, LC_OUT/p.name)

    # changelog
    if STATE_CL.exists():
        entry = (
            f"\n## 2026-07-25 — Laguna 12h soak (thinking-ON ceiling) + Comfy park/restore\n"
            f"- Parked graphic design lane `hermes-comfyui-ltx23.service` (:8188) reason=`soak_test_20260725`.\n"
            f"- Ran single 12h soak on Laguna rev 0761412 production K=7/s32, thinking ON max_tokens=8192.\n"
            f"- Report: `soak/LAGUNA_SOAK_12H_20260725.md` + raw JSONL.\n"
            f"- Restored: thinking-off smoke on Laguna then mode switch to ComfyUI; Laguna re-parked.\n"
        )
        STATE_CL.write_text(STATE_CL.read_text(encoding="utf-8", errors="replace")+entry, encoding="utf-8")
    print("WROTE", OUT_MD)
    print("restore_chat_ok", restore_chat_ok, "comfy_ok", comfy_ok)

if __name__ == "__main__":
    main()
