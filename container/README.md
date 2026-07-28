# Laguna S 2.1 NVFP4 + DFlash (Hermes recipe)

Independent DGX Spark / GB10 serving recipe for `poolside/Laguna-S-2.1-NVFP4`
with the matched DFlash draft. Flags derived from Poolside's HF card, public
community measurements, and an independent 20-cell K×seqs sweep on our own
benchmark protocol (2026-07-23). Not a fork of any third-party release contract.

## Profiles (SERVE_PROFILE env)

| Profile | K (DFlash) | max-num-seqs | Use |
|---------|-----------|--------------|-----|
| `production` (default) | 7 | 32 | best overall/code medians + multi-seq aggregate |
| `interactive` | 7 | 8 | best tool/prose medians, lighter scheduler |

Both: 12 GiB KV pin (`--kv-cache-memory-bytes 12884901888` ≈ 327K tokens of
fp8 KV), prefix caching + chunked prefill, batched 8192, FLASHINFER attention,
262,144 context, `top_k=20` temp 0.7 top_p 0.95, `VLLM_USE_DEEP_GEMM=0`
(measured inert on this path; pinned for explicitness).

## Build

Weights stay on the host. Never bake model weights into the image.

```bash
docker build --no-cache -t laguna-s21-nvfp4:hermes .
```

## Run

```bash
docker run --gpus all --ipc=host --shm-size 32g \
  --ulimit memlock=-1 --ulimit stack=67108864 \
  -e HOST=0.0.0.0 -e PORT=8000 -e SERVE_PROFILE=production \
  -v /path/to/models/hf:/models/hf \
  -p 8000:8000 laguna-s21-nvfp4:hermes
```

First start takes ~10 to 15 min (weight load + FlashInfer JIT + CUDA graph
capture). Mount a persistent FlashInfer cache to speed later starts. Private
binds: set `-e HOST=<your-ip>`; no operator IPs are baked into the image.

The entrypoint fails closed: missing weights/draft mounts, unknown profile, or
a broken FlashInfer install refuse to serve (`HERMES_LAUNCH_REJECTED`), and it
prints the effective vllm cmdline before exec.

## Measured (conditions matter)

Hermes bench v1 (our protocol: agent-shaped prompts, depths 1 to 64K, streaming,
decode=(n−1)/(t_last−t_first)), single GB10, production profile: c=1 overall
median 23.4 tok/s; code median 45.8; prose floor 18.4; c=4 aggregate 61.7;
TTFT ~330 ms. Cold long-context (no prefix-cache reuse): 100K tokens → TTFT
45.6 s, decode ~19 tok/s; 209K → TTFT 133 s, decode ~14 to 18 tok/s.

See `VERSIONS.md` for every pin (base digest, FlashInfer wheel sha256s, model
and draft revisions).

## License

Hermes-original scripts: MIT. Third-party: vLLM/FlashInfer Apache-2.0; model
weights under Poolside's OpenMDW-1.1 (not distributed in this image).
