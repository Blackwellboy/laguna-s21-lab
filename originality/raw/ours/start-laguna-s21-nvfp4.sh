#!/usr/bin/env bash
# Laguna S 2.1 NVFP4 — BEAT r0b0tlab contract (0761412 + max-speed flags)
# Base parity: vLLM 0.25.1, SM121 FLASHINFER_CUTLASS, FP8 KV, poolside parsers
# Beat deltas vs r0b0tlab K=7/seqs=32: K=6, max-num-seqs=4, prefix+chunked, KV pin 12GiB, DEEP_GEMM=0
set -euo pipefail
export PATH="/usr/local/cuda/bin:$HOME/.local/bin:$PATH"
export CUTE_DSL_ARCH=sm_121a
export MAX_JOBS=4
export NVCC_THREADS="${NVCC_THREADS:-2}"
export FLASHINFER_NVCC_THREADS="${FLASHINFER_NVCC_THREADS:-2}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-4}"
export VLLM_USE_FLASHINFER_SAMPLER="${VLLM_USE_FLASHINFER_SAMPLER:-1}"
export VLLM_USE_DEEP_GEMM="${VLLM_USE_DEEP_GEMM:-0}"
export HF_HOME="${HF_HOME:-$HOME/models/hf}"
VENV="$HOME/venvs/laguna-vllm025"
# Prefer 0761412 dir when complete, else legacy
if [[ -f $HF_HOME/poolside--Laguna-S-2.1-NVFP4-0761412/model.safetensors.index.json ]]; then
  MODEL_DIR="$HF_HOME/poolside--Laguna-S-2.1-NVFP4-0761412"
else
  MODEL_DIR="$HF_HOME/poolside--Laguna-S-2.1-NVFP4"
fi
DRAFT_DIR="$HF_HOME/poolside--Laguna-S-2.1-DFlash-NVFP4"
BIND_HOST="${LAGUNA_BIND_HOST:-0.0.0.0}"
PORT="${LAGUNA_PORT:-8000}"
# Tunables: set LAGUNA_PROFILE=r0b0tlab to match their contract; default=beat
PROFILE="${LAGUNA_PROFILE:-beat}"
if [[ "$PROFILE" == "r0b0tlab" ]]; then
  NUM_SPEC=7; MAX_SEQS=32; KV_BYTES=""; EXTRA_PREFIX=()
else
  NUM_SPEC=6; MAX_SEQS=4; KV_BYTES=12884901888; EXTRA_PREFIX=(--enable-prefix-caching --enable-chunked-prefill)
fi
mkdir -p "$HOME/logs/laguna"
source "$VENV/bin/activate"
ARGS=(
  vllm serve "$MODEL_DIR"
  --served-model-name poolside/Laguna-S-2.1-NVFP4
  --speculative-config "{\"model\":\"$DRAFT_DIR\",\"num_speculative_tokens\":${NUM_SPEC},\"method\":\"dflash\"}"
  --enable-auto-tool-choice
  --tool-call-parser poolside_v1
  --reasoning-parser poolside_v1
  --override-generation-config '{"temperature":0.7,"top_p":0.95,"top_k":20}'
  --attention-backend FLASHINFER
  --kv-cache-dtype fp8
  --dtype bfloat16
  --max-num-batched-tokens 8192
  --max-num-seqs "$MAX_SEQS"
  --max-model-len 262144
  --gpu-memory-utilization 0.85
  --host "$BIND_HOST"
  --port "$PORT"
)
if [[ -n "$KV_BYTES" ]]; then ARGS+=(--kv-cache-memory-bytes "$KV_BYTES"); fi
ARGS+=("${EXTRA_PREFIX[@]}")
exec "${ARGS[@]}"
