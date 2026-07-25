# Laguna S 2.1 NVFP4 + DFlash container (Hermes / single DGX Spark recipe)

## Why these flags
- `CUTE_DSL_ARCH=sm_121a` + FlashInfer nightly: native NVFP4 on GB10
- `method=dflash` + `num_speculative_tokens=7`: forum consensus that n=15 wastes drafts (pos 6-15 accept ~0)
- `top_k=20`: HF eval-certified sampling with temp 0.7 / top_p 0.95
- `max-num-seqs 32`: DFlash crashes at default 256
- `MAX_JOBS=4`: uncapped JIT can OOM 128GB unified memory
- prefix-caching + chunked-prefill: multi-turn / agent harness TTFT

## Build / run
Weights stay on host (~72GB). Do not bake weights into the image.

```bash
docker build -t laguna-s21-nvfp4:local ~/containers/laguna-s21-nvfp4
docker run --gpus all --ipc=host \
  --ulimit memlock=-1 --ulimit stack=67108864 \
  -e CUTE_DSL_ARCH=sm_121a -e MAX_JOBS=4 \
  -v $HOME/models/hf:/models/hf \
  -p 8000:8000 laguna-s21-nvfp4:local
```

Private private-network bind: set `-e HOST=<YOUR_BIND_IP>` and map accordingly.
