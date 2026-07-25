# TWEET PACK v3 — Laguna S 2.1 NVFP4 on a single DGX Spark (claim-safe rewrite, 2026-07-23)

STATUS: DRAFTS ONLY — no posting. Bracketed [SWEEP-*] values arrive from the
20-cell tuning session; do not fill them by hand, and do not post before the
container runbook has produced a clean build if tweet 6 is used.

Per-claim safety basis: prepub review table 2026-07-23. Rules applied:
no "beat" language in any form; medians labeled median, peaks labeled peak;
long-context claims are retrieval-proof only (no latency/throughput); container
claims deferred until a clean build exists.

---

## Tweet 1 — the setup (SAFE)

Laguna S 2.1 NVFP4 + matched DFlash draft, serving on a single DGX Spark (GB10,
128 GB unified). vLLM 0.25.1, FLASHINFER attention, FP8 KV, 262,144-token
context. Weights pinned to checkpoint 0761412. Full recipe + flags below 🧵

## Tweet 2 — own benchmark protocol (SAFE)

We wrote our own benchmark instead of reusing anyone's harness: agent-shaped
prompts (tool-calling, code refactor, strict-JSON, prose) at 1K/3K/6K context
depths, streaming, decode measured as (tokens−1)/(t_last−t_first), c=1 and c=4.
Harness is published — run it against your own box.

## Tweet 3 — honest numbers (SAFE — medians labeled)

On our protocol at c=1: code ~[SWEEP-CODE-MEDIAN] tok/s median (peaks higher on
long code gens), tool-calling ~[SWEEP-TOOL-MEDIAN], strict-JSON
~[SWEEP-JSON-MEDIAN], prose floor ~[SWEEP-PROSE-MEDIAN]. TTFT ~[SWEEP-TTFT] ms.
Prose is the honest floor — speculative decoding helps code far more than prose.

## Tweet 4 — the A/B we didn't expect (SAFE — credits the reference)

We A/B'd our interactive profile (K=6, 4 seqs, 12 GiB KV pin) against a
r0b0tlab-style profile (K=7, 32 seqs) on the same box under our own bench —
and their-style profile came out ahead on c=1 medians (~23.4 vs ~21.8 overall).
Respect. So we stopped guessing and swept the whole space.

## Tweet 5 — the sweep derivation (SAFE once numbers land)

20-cell sweep: DFlash K ∈ {5..9} × max-num-seqs ∈ {4,8,16,32}, everything else
pinned (FP8 KV, FLASHINFER, 256K, prefix caching on). Winner:
K=[SWEEP-K], seqs=[SWEEP-SEQS] → promoted to production
([SWEEP-WINNER-HEADLINE] tok/s c=1 overall median, [SWEEP-C4] tok/s c=4
aggregate). Full grid table in the repo — including the cells that lost.

## Tweet 6 — container (HOLD until clean build + smoke parity exist)

Thin container recipe: FROM vllm/vllm-openai:v0.25.1 + FlashInfer nightly
pinned by version AND wheel sha256, weights mounted at runtime, no secrets
baked in. Clean --no-cache build, smoke-tested within 5% of our bare-venv
service. ghcr.io/blackwellboy/laguna-s21-nvfp4

## Tweet 7 — long context (SAFE — retrieval-proof only)

Long-context sanity: needle retrieval verified at ~100K and ~180K real prompt
tokens on the live 262,144 config. With a 12 GiB KV pin that's ~327K tokens of
KV — one full-256K session plus headroom (not two). Honest ceiling and cold-run
methodology in the repo.

## Tweet 8 — provenance (SAFE)

Flag provenance is documented line-by-line: Poolside's official Spark recipe as
base, single-stream tuning measured by howtospark + MiaAI-Lab community work,
our own sweep for the final pair. Similarity vs other public Laguna containers:
entrypoint 0.12 / Dockerfile 0.05 (SequenceMatcher) — raw diff corpus published.

---

## Explicitly banned phrasings (do not reintroduce)

- "beat/beats/beating r0b0tlab", "fastest Laguna on Spark"
- "46–50 tok/s code" without the word *peak* next to it
- any tok/s or latency figure at 100K+ context (cache-warm data retired;
  cold numbers only after the Phase-3 cold probe lands)
- "publishable container" / digest claims before the runbook is executed
- anything implying we ran their 8,620-case quality battery
