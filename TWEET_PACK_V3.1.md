# TWEET PACK v3.1 — Laguna S 2.1 NVFP4 on a single DGX Spark (final numbers, 2026-07-24)

STATUS: DRAFTS ONLY — no posting without operator explicit go. Tweet 6 is HOLD:
the container build is blocked on a docker-daemon repair (buildkit DB), so no
container claim is currently verified.

Framing (non-negotiable): the story is **convergence** — we swept the space
independently and converged on the same optimum another publisher qualified,
cross-validating it, while mapping landscape a point-qualification can't show.
No "beat" language. Medians labeled median. Long-context = cold numbers only.
No claim rests on unverifiable posts.

---

## Tweet 1 — the setup (SAFE)

Laguna S 2.1 NVFP4 + matched DFlash draft, serving on a single DGX Spark
(GB10, 128 GB unified). vLLM 0.25.1, FLASHINFER attention, FP8 KV,
262,144-token context, checkpoint 0761412. Full recipe, flags, and our own
benchmark protocol below 🧵

## Tweet 2 — own benchmark protocol (SAFE)

We wrote our own benchmark instead of reusing anyone's harness: agent-shaped
prompts (tool-calling, code refactor, strict-JSON, prose) at 1K–64K context
depths, streaming, decode = (tokens−1)/(t_last−t_first), c=1 and c=4. Harness
published — run it against your own box.

## Tweet 3 — honest numbers (SAFE — medians labeled)

Production profile on our protocol, c=1 decode medians: **code 45.8 tok/s**,
tool 26.8, strict-JSON 19.3, **prose floor 18.4** — overall median 23.4.
c=4 aggregate 61.7 tok/s. TTFT ~330 ms. Still >20 tok/s at 64K depth.
Prose is the honest floor: speculative decoding pays on code, not free prose.

## Tweet 4 — the sweep (SAFE — the convergence story)

We didn't guess the config. 20-cell sweep: DFlash K∈{5..9} × max-num-seqs
∈{4,8,16,32}, everything else pinned. Winner: **K=7, seqs=32** — the same pair
r0b0tlab qualified independently. Two independent methods, same optimum.
That's cross-validation, and it's worth more than a rivalry.

## Tweet 5 — what the map shows that a point can't (SAFE)

The landscape around the optimum: K=8 and K=9 collapse everywhere (DFlash
per-position acceptance ≈0 past position 3 — deeper drafts are pure waste),
and our short-bench leader (K6s16) evaporated under the full matrix — a
lucky-window mirage. Sweeps catch what single-point qualifications and quick
benches can't. Full grid table published, losing cells included.

## Tweet 6 — container (HOLD — parity pending; build/identity now verified)

[STILL HOLD — do not post until parity passes in an authorized service window.
VERIFIED as of 2026-07-24 and safe to claim once un-held: clean --no-cache
build; base pinned by digest (vllm-openai:v0.25.1@sha256:e4f88a83…); FlashInfer
nightly trio pinned by version AND wheel sha256; weights mounted, never baked;
fail-closed entrypoint (proven live — a bad install killed the build).
NOT yet verified, must not be claimed: any performance/parity number for the
container. Draft on parity PASS: "…and smoke parity within ±5% decode /
±15 ms TTFT of our bare-venv service, same box, same protocol."]

## Tweet 7 — long context, cold (SAFE)

Cold long-context (no prefix-cache reuse, measured not extrapolated):
100K-token prompt → first token in 45.6 s, then ~19 tok/s decode. 209K →
first token 133 s, ~14–18 tok/s. Needle retrieval verified at both depths.
With the 12 GiB KV pin (~327K tokens) that's one full-256K session plus
headroom — capacity math and methodology in the repo.

## Tweet 8 — provenance (SAFE)

Every flag has a dated source: Poolside's card as base; community
measurements (NVIDIA forum, MiaAI-Lab, howtospark, eugr) for the tuning
directions — archived with dates, K=7 was on the forum before any container
release — and our own sweep for the final pair. Similarity vs other public
Laguna containers: entrypoint 0.12 / Dockerfile 0.05 (SequenceMatcher); raw
diff corpus published.

---

## Banned phrasings (unchanged)

- "beat/beats/beating r0b0tlab", "fastest Laguna on Spark"
- code figures without the word *median* (peaks only with explicit conditions)
- any warm-cache latency figure at depth; any claim from the two unlocatable
  X posts; any container claim while tweet 6 is HOLD
- anything implying we ran their 8,620-case quality battery
