#!/usr/bin/env bash
set -euo pipefail
MODEL_DIR="${MODEL_DIR:-/models/hf/poolside--Laguna-S-2.1-NVFP4}"
DRAFT_DIR="${DRAFT_DIR:-/models/hf/poolside--Laguna-S-2.1-DFlash-NVFP4}"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
export CUTE_DSL_ARCH="${CUTE_DSL_ARCH:-sm_121a}"
export MAX_JOBS="${MAX_JOBS:-4}"
export VLLM_USE_DEEP_GEMM="${VLLM_USE_DEEP_GEMM:-0}"
export VLLM_USE_FLASHINFER_SAMPLER="${VLLM_USE_FLASHINFER_SAMPLER:-1}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-4}"
exec vllm serve "$MODEL_DIR" \
  --served-model-name poolside/Laguna-S-2.1-NVFP4 \
  --speculative-config "{\"model\":\"$DRAFT_DIR\",\"num_speculative_tokens\":${NUM_SPEC:-6},\"method\":\"dflash\"}" \
  --enable-auto-tool-choice \
  --tool-call-parser poolside_v1 \
  --reasoning-parser poolside_v1 \
  --override-generation-config '{"temperature":0.7,"top_p":0.95,"top_k":20}' \
  --enable-prefix-caching \
  --enable-chunked-prefill \
  --max-num-batched-tokens "${MAX_BATCHED_TOKENS:-8192}" \
  --max-num-seqs "${MAX_NUM_SEQS:-4}" \
  --max-model-len "${MAX_MODEL_LEN:-262144}" \
  --gpu-memory-utilization "${GPU_MEM_UTIL:-0.85}" \
  --kv-cache-memory-bytes "${KV_CACHE_BYTES:-12884901888}" \
  --host "$HOST" \
  --port "$PORT"
