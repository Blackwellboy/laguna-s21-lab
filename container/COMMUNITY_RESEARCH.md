# Community deep-dive (2026-07-23)

## howtospark.com (measured gold on single Spark)
- k=6 peak: 42.9 tok/s code vs 18.9 no-draft (2.3x)
- max-num-seqs=4 (+6-7% vs 2) because CUDA graph = seqs×(k+1)
- kv-cache-memory-bytes=12GiB pin
- k=15 crater acceptance (31%) and can underperform k=6

## MiaAI-Lab Docker (vllm/vllm-openai:v0.25.1)
- FlashInfer nightly bootstrap 0.6.15.dev20260712
- max-num-seqs 4, num_spec 7, attention-backend FLASHINFER
- shm 32g, ipc host, CUTE_DSL_ARCH=sm_121a

## eugr/spark-vllm-docker
- Community Spark image with mods/drop-caches, OMP=4, FLASHINFER_SAMPLER
- multi-node recipes; InstantTensor load-format optional

## X community
- @darvasch: DFlash 3x on code OR slower than 19 tok/s on agent reasoning — use DFlash selectively
- @sudoingX: 25-30 chat, 45 code, ~140 aggregate @16 streams
- @stevibe: Spark 19.44, PRO6000 108, 4x5090 145
- Forum: n=7 better than 15 for many; some claim 40-50

## Our pack
num_spec=6, max-num-seqs=4, kv pin 12GiB, DEEP_GEMM=0, prefix+chunked, top_k=20
