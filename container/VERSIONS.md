# Pinned versions (Hermes Laguna S 2.1 NVFP4 container)

Captured at the clean `--no-cache` build of 2026-07-24 (build log retained).

| Component | Pin |
|-----------|-----|
| Base image | `vllm/vllm-openai:v0.25.1@sha256:e4f88a835143cd22aee2397a26ec6bb80b3a4a6fe0c882bcbc63822904766089` |
| Built image Id | `sha256:44ce557a76bb327c5bf42bef8db488eae52aee2e7fe629f47851f148a08a96c8` |
| vLLM (in-image, verified) | 0.25.1 |
| flashinfer-python | `0.6.15.dev20260712` — wheel sha256 `a5db054f9a5884bd6d826e9ddd2053a72b3c3fb2cb9347662203cb70f8b964ab` |
| flashinfer-cubin | `0.6.15.dev20260712` — wheel sha256 `11ef5704ae519a0b31a8551fad4c94efee15fa6109756c34a5c7aed13830d8b3` |
| flashinfer-jit-cache | `0.6.15.dev20260712+cu130` (aarch64) — wheel sha256 `3eeca9b82500396c0de8b3ceacc45affa5cb960bfeba611ed6247a179a39f1a9` |
| Target model | poolside/Laguna-S-2.1-NVFP4@07614121b31898586430f189d27a25a0be310843 |
| Draft model | poolside/Laguna-S-2.1-DFlash-NVFP4@723794750422b3efbf3a7b3af76dffb4ba035943 |
| CUTE_DSL_ARCH | sm_121a |
| Default profile | production (K=7, max-num-seqs=32, KV pin 12 GiB, prefix+chunked, batched 8192) |
| Alternate profile | interactive (K=7, max-num-seqs=8) |
| VLLM_USE_DEEP_GEMM | 0 (measured inert on NVFP4 compressed-tensors path, 2026-07-23) |

Install note: the FlashInfer trio installs with stock pip (`--no-deps`, exact
`==` pins, nightly + cu130 extra indexes). The build fails closed on any
FlashInfer install/pin mismatch (in-Dockerfile version assert).

Parity smoke (container vs bare-venv reference, same box/protocol/network path):
**PENDING** — the 67 GiB weights cannot co-reside with the serving reference on
one 121 GiB GB10 (container correctly failed closed: "Free memory 22.75 GiB <
required"). Parity needs a brief reference-service window; not yet run. No
performance claim is made for this image until that parity PASSES.
