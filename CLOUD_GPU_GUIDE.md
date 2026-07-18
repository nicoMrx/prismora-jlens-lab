# Cloud GPU worker guide

The control plane does not need to know which GPU vendor is used. It only needs
a protected URL implementing:

```text
GET  /v1/health
GET  /v1/capabilities
POST /v1/run       body: {"request": <PlannedRun.request>}
```

## Recommended deployment pattern

1. Keep the control plane on a persistent CPU instance or local machine.
2. Build a worker image that pins:
   - model weight revision or content hash;
   - tokenizer revision/hash;
   - J-Lens code commit;
   - lens checkpoint hash;
   - PyTorch, Transformers, CUDA and kernel versions;
   - precision and quantization policy.
3. Load one model per worker process. Do not silently swap models behind one worker identity.
4. Mount a read-only model cache where possible.
5. Expose the worker only through TLS and bearer authentication, VPN or private network.
6. Set a hard provider-side spending limit and automatic instance termination policy.
7. Store raws on the persistent control plane before terminating the GPU.

## Runtime choices

### Supplied readout-only reference runtime

Install `requirements-gpu.txt`, then configure:

```bash
PRISMORA_WORKER_RUNTIME=prismora_worker.hf_jlens_runtime:create_runtime
```

This path loads one pinned HuggingFace decoder and one pre-fitted Anthropic
`JacobianLens`. It supports exact-token replay plus Jacobian and Logit read-outs.
It rejects interventions and fitting. See `GPU_RUNTIME_REFERENCE.md`.

Before model loading:

```bash
prismora-worker-preflight
```

After the environment passes, the expensive check is:

```bash
prismora-worker-preflight --load
```

A provider-neutral container shell is supplied in `Dockerfile.gpu.reference`
and `docker-compose.gpu.reference.yml`; select the CUDA/PyTorch base image by
immutable digest rather than relying on a moving tag.

### Private causal runtime

Copy `prismora_worker/runtime_template.py` into a private deployment package and
implement `capabilities()` and `run()`. Then configure:

```bash
PRISMORA_WORKER_RUNTIME=my_runtime:create_runtime
```

Every runtime must return actual layer numbers and exact token IDs. It must
report model/tokenizer/lens revisions and any precision or quantization. It must
reject unsupported interventions rather than approximating them silently.

## Bridge validation before cross-backend merging

For one model that is available publicly and locally:

1. Pin identical weights, tokenizer and lens.
2. Run once publicly and capture all returned token IDs.
3. Replay the exact IDs publicly and privately with generation disabled.
4. Use Comparison Studio → **strict public/private bridge** to compare every position, actual layer, lens, ranked top-k token string and probability.
5. Record numerical tolerances by precision.
6. Do not merge public/private corpora until residual discrepancies are explained.

## Scientific GPU readiness checklist

- [ ] Public immutable image digest.
- [ ] Pinned model/tokenizer/lens revisions.
- [ ] `float32` lens checkpoint storage and finite-value checks.
- [ ] Explicit model precision and quantization.
- [ ] Actual layer map in every result.
- [ ] Exact-token replay test.
- [ ] Random-direction intervention controls.
- [ ] Crash-safe checkpoint/restart behavior.
- [ ] Provider budget ceiling and shutdown rule.
- [ ] Reproducibility bundle generated before instance deletion.
