# Laguna S 2.1 NVFP4 + DFlash for DGX Spark / GB10 (SM121) — Hermes recipe.
# Weights are mounted at runtime; this image is runtime only.
# Pins: see VERSIONS.md (base digest + FlashInfer wheel sha256 recorded at build).
FROM vllm/vllm-openai:v0.25.1
ENV CUTE_DSL_ARCH=sm_121a \
    MAX_JOBS=4 \
    NVCC_THREADS=2 \
    FLASHINFER_NVCC_THREADS=2 \
    OMP_NUM_THREADS=4 \
    VLLM_USE_FLASHINFER_SAMPLER=1 \
    VLLM_USE_DEEP_GEMM=0 \
    HF_HOME=/models/hf \
    PATH=/usr/local/cuda/bin:$PATH
USER root
RUN apt-get update && apt-get install -y --no-install-recommends python3-dev \
  && rm -rf /var/lib/apt/lists/*
# FlashInfer matched nightly trio for native NVFP4 on sm_121.
# FAIL-CLOSED: no soft-fail — a failed install must kill the build (mismatched
# FP4 kernels silently collapse DFlash draft acceptance). --no-deps prevents
# the resolver from moving the base image's stack.
RUN pip install --no-cache-dir --no-deps \
  "flashinfer-python==0.6.15.dev20260712" \
  "flashinfer-cubin==0.6.15.dev20260712" \
  "flashinfer-jit-cache==0.6.15.dev20260712+cu130" \
  --extra-index-url https://flashinfer.ai/whl/nightly/ \
  --extra-index-url https://flashinfer.ai/whl/nightly/cu130/ \
 && python3 -c "import flashinfer, importlib.metadata as md; assert flashinfer.__version__.startswith('0.6.15.dev20260712'), flashinfer.__version__; assert md.version('flashinfer-jit-cache') == '0.6.15.dev20260712+cu130', md.version('flashinfer-jit-cache'); print('flashinfer pin verified:', flashinfer.__version__)"
WORKDIR /workspace
COPY entrypoint.sh /entrypoint.sh
COPY VERSIONS.md /VERSIONS.md
COPY README.md /README.md
RUN chmod +x /entrypoint.sh
EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
