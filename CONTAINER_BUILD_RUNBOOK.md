# CONTAINER BUILD RUNBOOK: Laguna S 2.1 NVFP4 (deferred until sweep completes)

Target host: the DGX Spark serving host (venv service must be healthy; it is the
parity reference). Est. 20 min execution + one image build. Run only AFTER the
tuning sweep has finished and the final production profile is promoted, so the
smoke comparison is against the real production config.

## 0. Preconditions

```bash
systemctl --user is-active hermes-laguna-s21-nvfp4.service   # must be: active
curl -s http://$LAGUNA_BIND_HOST:8000/v1/models | head -c 200 # must return model
sudo systemctl start docker    # daemon was down 2026-07-23; start it
docker info | grep -E 'Server Version|Storage'                # sanity
df -h /var/lib/docker          # need ~25 GB free
```

If the final production profile from the sweep differs from the recipe defaults
(K=6/seqs=4), FIRST update `containers/laguna-s21-nvfp4/entrypoint.sh` defaults
(NUM_SPEC / MAX_NUM_SEQS / KV_CACHE_BYTES) to the promoted values and record the
change in VERSIONS.md.

## 1. Clean build (no cache) + identity capture

```bash
cd ~/containers/laguna-s21-nvfp4
docker build --no-cache -t laguna-s21-nvfp4:hermes . 2>&1 | tee /tmp/laguna_build.log

# capture identities for VERSIONS.md:
docker image inspect laguna-s21-nvfp4:hermes --format '{{.Id}}'
docker image inspect vllm/vllm-openai:v0.25.1 --format '{{json .RepoDigests}}'
```

## 2. FlashInfer wheel hash capture (pin-by-content, not just version)

```bash
docker run --rm --entrypoint bash laguna-s21-nvfp4:hermes -c '
  pip download flashinfer-python==0.6.15.dev20260712 flashinfer-cubin==0.6.15.dev20260712 \
      flashinfer-jit-cache==0.6.15.dev20260712 \
      --no-deps -d /tmp/w \
      --extra-index-url https://flashinfer.ai/whl/nightly/ \
      --extra-index-url https://flashinfer.ai/whl/nightly/cu130/ \
      --index-strategy unsafe-best-match >/dev/null 2>&1
  sha256sum /tmp/w/*'
# paste the three sha256 lines into VERSIONS.md ("FlashInfer wheel sha256" rows)
```

(Alternative if download differs from installed: `pip show -f` the installed dists
inside the image and hash the site-packages dist-info RECORD files.)

## 3. Smoke run (does not disturb the venv service: different port)

```bash
docker run -d --name laguna-smoke --gpus all --ipc=host \
  --ulimit memlock=-1 --ulimit stack=67108864 \
  -e HOST=127.0.0.1 -e PORT=8001 --network host \
  -v $HOME/models/hf:/models/hf \
  laguna-s21-nvfp4:hermes

# readiness (weight load ~10-15 min):
until curl -sf http://127.0.0.1:8001/v1/models >/dev/null; do sleep 20; done
```

## 4. 5%-parity protocol (venv vs container, same box, same prompts)

Use the Hermes bench harness in quick mode against BOTH endpoints back-to-back:

```bash
# venv service (production port 8000):
HERMES_BENCH_BASE=http://<BIND_HOST>:8000/v1 HERMES_BENCH_PROFILE=venv_parity \
  python3 hermes_bench_v1.py --quick
# container (port 8001):
HERMES_BENCH_BASE=http://127.0.0.1:8001/v1 HERMES_BENCH_PROFILE=container_parity \
  python3 hermes_bench_v1.py --quick
```

PASS criterion: container `overall_median_decode_c1` and `code` median within
**±5%** of the venv run, AND TTFT median within ±15 ms. Record both JSONs next
to the build log. If outside 5%: check the container actually took the same
flags (`docker exec laguna-smoke cat /proc/1/cmdline | tr '\0' ' '`) before
suspecting the image.

## 5. Teardown + record

```bash
docker rm -f laguna-smoke
```

Then update `VERSIONS.md` with: image Id, base RepoDigest, three FlashInfer wheel
sha256s, parity numbers + date, and the exact serve flags the smoke ran with.
Only after that is the container claim ("clean build, smoke parity within 5%,
all versions pinned") publishable.
