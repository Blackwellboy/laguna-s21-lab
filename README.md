# Laguna S 2.1 Testing Lab — DGX Spark (GB10)

Independent testing lab for **poolside Laguna S 2.1 (NVFP4)** served on a single
NVIDIA DGX Spark (GB10, 128 GB unified memory) with vLLM. Everything here is the
raw material behind the numbers posted publicly the week of 2026-07-20:

- a **20-cell tuning sweep** (K × max-num-seqs grid) with every cell's raw JSON,
  including the losers;
- a **container recipe** with pinned image/base digests and wheel checksums;
- **hermes_bench_v1**, the benchmark harness used for every throughput number;
- a **12-hour production soak** with raw per-turn logs (3,099 turns), incident
  log, integrity probes, and service memory samples.

One operator, one box, single runs scoped as such. Model revision **0761412**
everywhere. Where a number depends on a condition, the condition is stated next
to the number.

## Repo map

| Path | What it is |
|------|-----------|
| `container/` | Dockerfile, entrypoint, VERSIONS.md (pinned digests + wheel sha256s), build runbook context |
| `bench/hermes_bench_v1.py` | The harness. Streaming decode measured as (n−1)/(t_last−t_first), TTFT separate, per-category (tool/code/json/prose) and per-depth rows |
| `bench/results/` | Reference + interactive profile results; `full/` holds the full-protocol runs behind the headline medians |
| `sweep/` | `LAGUNA_TUNING_SWEEP_20260723.md` (protocol + full grid + analysis) and `cells/` — all 21 raw per-cell JSONs |
| `longctx/` | Cold long-context probe script + raw JSON (nonce defeats prefix cache from position 0) |
| `soak/` | 12h soak: driver, runner, score/restore scripts, results report, and `logs/` with raw `turns.jsonl`, `sessions.jsonl`, `incidents.jsonl`, `integrity_probes.jsonl`, `service_samples.jsonl` |
| `originality/` | Side-by-side raw corpus of our container files vs r0b0tlab's published recipe, plus the similarity audit |
| `SOURCE_ARCHIVES*` | Dated archive links for every community source used |
| `TWEET_PACK_V3.1.md` | The claim set as posted, kept verbatim for accountability |
| `REDACTIONS.md` | Exact sanitization applied to these files before publication |

## Headline findings (conditions attached)

**Tuning sweep (2026-07-23, 20 cells, K∈{5..9} × seqs∈{4,8,16,32}):**
production winner **K=7 / max-num-seqs=32** — same flag pair r0b0tlab qualified
independently, derived here by measurement, with three deliberate config
differences retained (prefix caching ON, chunked prefill ON, 12 GiB KV pin).
**K≥8 collapses throughput** on this stack (see the grid — the losers are
published too). Every cell: full service restart, cmdline verification, warmup,
then the short bench subset. Single run per cell.

**Full bench @ K7/s32** (`bench/results/full/hermes_bench_v1_full_K7s32_*.json`,
236 rows): code decode **45.8 tok/s median**, prose floor **18.4**, overall
median **23.4** single-stream, c=4 aggregate **61.7**, TTFT **~330 ms**. FP8 KV,
FLASHINFER, 262,144 ctx.

**Cold long-context** (`longctx/`, cold-prefill via nonce): 100K tokens → TTFT
**45.6–45.7 s**, decode ~18–19 tok/s; 209K tokens → TTFT **~133 s**, decode
~14–18 tok/s; retrieval needle found in 4/4 runs. These are honest cold numbers;
warm/prefix-cached figures appear nowhere in our claims.

**12h production soak (2026-07-24→25, single run):** thinking-ON with a client
`max_tokens=8192` ceiling, production K7/s32 profile, poolside_v1 parsers,
prefix caching on. **409 sessions / 3,099 turns, 3,096 HTTP-200 (99.9%), zero
crashes, zero service restarts**, ~4.1 GiB RSS creep over 12h, ~13.5 s mean
turn latency. **9 incidents, all `session_cap`** — the driver's own token-cap
guard killing runaway-context sessions by design; zero unbounded-generation
loops observed. Integrity probes: **3/3 refused** a planted fake-credential
history-rewrite task (the `TESTONLY_sk_live_…` string in the logs is a clearly
labeled fake planted by the probe).

**Checkpoint note (added 2026-07-26):** the figures posted publicly (and cited
"as stated" in TheTom's guide §5d: ~389 sessions, ~2,947 turns, 2,944 OK,
~11.5h of tool work) reference an **~11.5-hour checkpoint** taken before the
run finished. The final logs in `soak/logs/` run **409 sessions / 3,099 turns /
3,096 HTTP-200**. Same run, later cut; the success rate is 99.9% at either
checkpoint.

**Two precision caveats on the soak, stated up front:**

1. **Thinking routing rate ~0.1%** (3 of 3,096 turns fired thinking). The API
   returned empty `reasoning` fields even when thinking was explicitly
   requested, so on this rev the measured rate may be partly a
   template/parser-level artifact rather than a pure router property. It
   quantifies observable routing, not internal chain-of-thought.
2. **"Zero loops" is scoped**: zero unbounded-generation loops *while the
   thinking gate barely opened*. It is not a claim about thinking-heavy
   workloads.

## Reproducing

- **Container:** `container/` — build with the pinned base
  (`vllm/vllm-openai:v0.25.1@sha256:e4f88a…`), FlashInfer trio pinned with
  recorded sha256s, fail-closed install (a wrong flag aborts the build — proven
  live). Entrypoint prints the effective cmdline flag-by-flag. Weights are not
  in the image; mount your own copy of the rev-0761412 checkpoint.
- **Bench:** point `bench/hermes_bench_v1.py` at any OpenAI-compatible endpoint
  and compare row-level JSON, not just medians.
- **Sweep:** protocol in `sweep/LAGUNA_TUNING_SWEEP_20260723.md` §1; each cell
  JSON records its exact profile, base URL shape, and per-row measurements.
- **Soak:** `soak/run_soak_12h.sh` drives `soak_driver.py` (session mix
  short/long/deep, two personas, tool tasks, integrity probes every ~4h,
  ~10-min service samples). `score_and_restore.py` scores the logs and restores
  the box afterwards. Set `LAGUNA_ENDPOINT` to your server. The scripts
  reference the operator's systemd unit names; adapt them to your service
  manager.

## Sanitization

Logs and scripts came from live runs on a private network. Before publication,
overlay-network IPs were replaced with `localhost`/`<SERVER>`, hostnames with
`spark-host`, usernames with `operator`, and internal control-plane paths with
`<CONTROL_PLANE>`/`workspace` placeholders. Benchmark values, timestamps, token
counts, and protocol parameters were not altered. `soak/logs/turns.jsonl`
contains truncated response previews (not full prompt payloads); the soak's
document corpus consisted of internal working notes about this same Laguna
campaign and is not included. The IP `10.0.1.42` appearing in some responses is
a model-invented example from a synthetic `probe_service` tool task, not real
infrastructure. Full details: `REDACTIONS.md`.

## Cross-validation & related work

TheTom's off-label behavioral guide for Laguna S 2.1 — held-out behavioral
battery on a different quant and serving stack (Q4_K_M on llama.cpp vs our
NVFP4 on vLLM), which converged on the same operating manual. This soak is
cited as external validation in its §5d, with our two precision caveats
applied as posted:
<https://github.com/TheTom/offlabel/blob/main/models/laguna-s-2.1.md>

Since publication, the conversation around that guide has produced findings
that bear directly on this repo's data:

- **Third-stack replication of the persona gate** (@Defilan, gfx1151 /
  llama.cpp / generic harness, `reasoning_content` known-good there): 6/6
  bare-prompt probes fired thinking vs 0/5 with a named professional persona
  ([offlabel#2](https://github.com/TheTom/offlabel/issues/2)). A cleaner
  re-measurement (interleaved arms, prompt cache off, fixed token budget) put
  the same gate at 10/18 vs 1/18
  ([offlabel#5](https://github.com/TheTom/offlabel/issues/5)) — the gate is
  real (p = 0.0014), less sharp than the first pass suggested.
- **Corrected `enable_thinking` kwarg model**
  ([offlabel#5](https://github.com/TheTom/offlabel/issues/5)): explicit
  `false` is the one structural off-switch (pre-closed `</think>`; 0/15
  reasoned). Omitting the kwarg **fires** on their llama.cpp path (the server
  overrides the template default; absent renders byte-identical to `true`),
  and explicit `true` fires. Note our rev-0761412 checkpoint's template
  defaults `enable_thinking` to `true` outright, consistent with the
  post-release config drift documented in the guide's changelog.
- **Cross-model integrity finding**: the housekeeping-framed provenance blind
  spot (and the system-prompt clause that closes it) reproduced on
  Qwen3.6-35B-A3B — 4 folds unprompted, 0 with the clause
  ([offlabel patterns.md](https://github.com/TheTom/offlabel/blob/main/patterns.md),
  data in [offlabel#2](https://github.com/TheTom/offlabel/issues/2)). Our
  soak's 3/3 refused integrity probes ran the same clause family on this
  stack.
- **Shared spine-probe runner** merged into the guide repo
  ([offlabel PR#3](https://github.com/TheTom/offlabel/pull/3),
  `scripts/spine-probes/`): drives any OpenAI-compatible endpoint, ablates
  the integrity clause rule by rule, re-scores transcripts offline.

### Known interpretation updates

- **2026-07-26 — the soak's ~0.1% thinking rate, reread under the corrected
  kwarg model.** The soak driver sent explicit
  `chat_template_kwargs: {"enable_thinking": true}` on every turn
  (`soak/soak_driver.py`). Per the corrected model in
  [offlabel#5](https://github.com/TheTom/offlabel/issues/5), explicit `true`
  is a **fires** arm: thinking was structurally available on every turn. The
  ~0.1% is therefore best read as **prompt-side suppression overriding an
  explicitly fired kwarg** under full named-persona agent prompts — not as
  the kwarg failing to arm, and not as evidence about the `false` path, which
  the soak never exercised.

## Credits

- **poolside** — Laguna S 2.1 (the model; weights under poolside's own terms,
  not included here).
- **howtospark, MiaAI-Lab, tonyd2wild, eugr** — community DGX Spark serving
  recipes that informed this work (dated archives in `SOURCE_ARCHIVES.md`).
- **r0b0tlab** — independent qualification of the K=7/seqs=32 pair,
  cross-validating the sweep result (raw corpus in `originality/`).
- **TheTom** — the off-label behavioral battery and guide linked above.

## Commercial

Independent model/quant verification, DGX Spark and local-inference deployment
engineering, and performance tuning, done the way this repo is done. DM
[@Blackwellboy on X](https://x.com/BlackwellBoy).

## License

MIT for everything in this repository (see `LICENSE`). Model weights are **not
included** and remain under poolside's license terms. Third-party raw files in
`originality/raw/r0b0tlab/` retain their upstream MIT license, reproduced
alongside them for independent verification.
