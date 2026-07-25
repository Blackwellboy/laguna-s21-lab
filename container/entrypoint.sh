#!/usr/bin/env bash
# Laguna S 2.1 NVFP4 + DFlash — Hermes container entrypoint (publishable).
# Contract: fail-closed, env-overridable, dual-profile, prints effective cmdline.
# Profiles (SERVE_PROFILE): production (default, K=7/seqs=32) | interactive (K=7/seqs=8)
set -euo pipefail

MODEL_DIR="${MODEL_DIR:-/models/hf/poolside--Laguna-S-2.1-NVFP4-0761412}"
DRAFT_DIR="${DRAFT_DIR:-/models/hf/poolside--Laguna-S-2.1-DFlash-NVFP4}"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"

export CUTE_DSL_ARCH="${CUTE_DSL_ARCH:-sm_121a}"
export MAX_JOBS="${MAX_JOBS:-4}"
export NVCC_THREADS="${NVCC_THREADS:-2}"
export FLASHINFER_NVCC_THREADS="${FLASHINFER_NVCC_THREADS:-2}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-4}"
export VLLM_USE_FLASHINFER_SAMPLER="${VLLM_USE_FLASHINFER_SAMPLER:-1}"
# Measured INERT on this NVFP4 path (Hermes A/B 2026-07-23); kept explicit.
export VLLM_USE_DEEP_GEMM="${VLLM_USE_DEEP_GEMM:-0}"

SERVE_PROFILE="${SERVE_PROFILE:-production}"
case "$SERVE_PROFILE" in
  production)  NUM_SPEC=7; MAX_NUM_SEQS=32 ;;
  interactive) NUM_SPEC=7; MAX_NUM_SEQS=8 ;;
  *) echo "HERMES_LAUNCH_REJECTED: unknown SERVE_PROFILE='$SERVE_PROFILE' (production|interactive)" >&2; exit 64 ;;
esac
# Explicit env overrides still win over the profile
NUM_SPEC="${NUM_SPEC_OVERRIDE:-$NUM_SPEC}"
MAX_NUM_SEQS="${MAX_NUM_SEQS_OVERRIDE:-$MAX_NUM_SEQS}"
MAX_BATCHED="${MAX_BATCHED_TOKENS:-8192}"
MAX_LEN="${MAX_MODEL_LEN:-262144}"
GPU_UTIL="${GPU_MEM_UTIL:-0.85}"
KV_BYTES="${KV_CACHE_BYTES:-12884901888}"

# Fail-closed preflight
[[ -f "$MODEL_DIR/config.json" ]] || { echo "HERMES_LAUNCH_REJECTED: target weights not mounted at $MODEL_DIR" >&2; exit 65; }
[[ -f "$DRAFT_DIR/config.json" ]] || { echo "HERMES_LAUNCH_REJECTED: DFlash draft not mounted at $DRAFT_DIR" >&2; exit 65; }
python3 - <<'PYEOF' || { echo "HERMES_LAUNCH_REJECTED: FlashInfer import failed — refusing to serve with mismatched/absent FP4 kernels" >&2; exit 66; }
import flashinfer
print(f"flashinfer {flashinfer.__version__} OK", flush=True)
PYEOF

ARGS=(
  vllm serve "$MODEL_DIR"
  --served-model-name "${SERVED_MODEL_NAME:-poolside/Laguna-S-2.1-NVFP4}"
  --speculative-config "{\"model\":\"$DRAFT_DIR\",\"num_speculative_tokens\":${NUM_SPEC},\"method\":\"dflash\"}"
  --enable-auto-tool-choice
  --tool-call-parser poolside_v1
  --reasoning-parser poolside_v1
  --override-generation-config '{"temperature":0.7,"top_p":0.95,"top_k":20}'
  --attention-backend FLASHINFER
  --kv-cache-dtype fp8
  --dtype bfloat16
  --enable-prefix-caching
  --enable-chunked-prefill
  --max-num-batched-tokens "$MAX_BATCHED"
  --max-num-seqs "$MAX_NUM_SEQS"
  --max-model-len "$MAX_LEN"
  --gpu-memory-utilization "$GPU_UTIL"
  --host "$HOST"
  --port "$PORT"
)
if [[ -n "$KV_BYTES" && "$KV_BYTES" != "0" ]]; then
  ARGS+=(--kv-cache-memory-bytes "$KV_BYTES")
fi

echo "HERMES_EFFECTIVE_PROFILE=$SERVE_PROFILE (K=$NUM_SPEC seqs=$MAX_NUM_SEQS)"
printf 'HERMES_EFFECTIVE_CMDLINE:'; printf ' %q' "${ARGS[@]}"; printf '\n'
exec "${ARGS[@]}"
