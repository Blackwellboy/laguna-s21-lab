# Hermetic Laguna S 2.1 NVFP4 + DFlash for DGX Spark / GB10 (SM121)
# Build: docker build -t laguna-s21-nvfp4:local .
# Run example (weights mounted, private-network bind):
# docker run --gpus all --ipc=host --ulimit memlock=-1 --ulimit stack=67108864 \
#   -e CUTE_DSL_ARCH=sm_121a -e MAX_JOBS=4 -e OMP_NUM_THREADS=4 \
#   -e VLLM_USE_FLASHINFER_SAMPLER=1 \
#   -v /path/to/models:/models -p 8000:8000 laguna-s21-nvfp4:local
FROM vllm/vllm-openai:v0.25.1
ENV CUTE_DSL_ARCH=sm_121a \
    MAX_JOBS=4 \
    OMP_NUM_THREADS=4 \
    VLLM_USE_FLASHINFER_SAMPLER=1 \
    HF_HOME=/models/hf \
    PATH=/usr/local/cuda/bin:$PATH
# FlashInfer nightly for native NVFP4 on sm_121 (pin matches hermes bring-up)
RUN pip install --no-cache-dir \
  "flashinfer-python==0.6.15.dev20260712" \
  "flashinfer-cubin==0.6.15.dev20260712" \
  "flashinfer-jit-cache==0.6.15.dev20260712" \
  --extra-index-url https://flashinfer.ai/whl/nightly/ \
  --extra-index-url https://flashinfer.ai/whl/nightly/cu130/ \
  --index-strategy unsafe-best-match || true
# python headers may be needed for Triton JIT on cold cache
USER root
RUN apt-get update && apt-get install -y --no-install-recommends python3-dev && rm -rf /var/lib/apt/lists/*
WORKDIR /workspace
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
