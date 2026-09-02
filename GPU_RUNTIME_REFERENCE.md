# Reference HuggingFace + Anthropic J-Lens runtime

`prismora_worker/hf_jlens_runtime.py` is the first non-synthetic worker path.
It follows the public Anthropic `jlens` API and is **readout-only** in v0.2:

- one pinned HuggingFace decoder model;
- one pinned tokenizer;
- one pre-fitted `JacobianLens` checkpoint;
- deterministic or sampled generation;
- exact `input_token_ids` replay;
- Jacobian Lens and vanilla Logit Lens top-k read-outs;
- exact layer numbers and token IDs;
- explicit local filter identity.

It rejects interventions, lens fitting, non-zero frequency penalties and model
IDs other than the one loaded at startup. This is intentional: unsupported
operations must fail, never become silent approximations.

## Required environment

```bash
export PRISMORA_WORKER_RUNTIME='prismora_worker.hf_jlens_runtime:create_runtime'
export PRISMORA_HF_MODEL_ID='Qwen/Qwen3.5-4B'
export PRISMORA_HF_MODEL_REVISION='<exact commit>'
export PRISMORA_HF_TOKENIZER_REVISION='<exact commit>'
export PRISMORA_JLENS_NAME_OR_PATH='neuronpedia/jacobian-lens'
export PRISMORA_JLENS_FILENAME='qwen3.5-4b/jlens/Salesforce-wikitext/Qwen3.5-4B_jacobian_lens_n1000.pt'
export PRISMORA_JLENS_REVISION='<exact commit or immutable revision>'
export PRISMORA_HF_DTYPE='bfloat16'
export PRISMORA_HF_DEVICE_MAP='auto'
export PRISMORA_WORKER_TOKEN='<long random secret>'
```

Validate the environment, then run:

```bash
prismora-worker-preflight
prismora-worker-preflight --load   # expensive: loads model + lens
python -m prismora_worker.app --host 0.0.0.0 --port 8100
```

## Important measurement distinction

`filter_nonword_tokens=true` uses `prismora-unicode-word-mask/v2-keep-raw-top1`. It is stored
in every raw `meta` record. It must not be assumed identical to Neuronpedia's
server-side filter. Public/private bridge validation should therefore compare
unfiltered read-outs first, then quantify filter differences separately.

## Validation status

The module is syntax-checked and its configuration/filter helpers are unit-tested
in the base environment. Loading a real model/lens and numerical comparison
require a CUDA worker and model downloads, which were unavailable during this
build. The bundled `jlens` dependency is pinned to Anthropic commit
`581d398613e5602a5af361e1c34d3a92ea82ba8e`.

## Second runtime: interp-engine (added 2026-09-02, static review, not CUDA-validated)

`prismora_worker/interp_engine_runtime.py` serves the same readout-only contract through
Neuronpedia's `interp-engine` (eager / vllm / vllm-static) while keeping this module's request
validation, the Anthropic `jlens` lens application and the Prismora word mask. It adds to `meta`:
`engine`, `engine_backend`, `compute_path` (`recompute` | `incremental`), `lens_sha256`, `lens_shape`.
Select it with `PRISMORA_WORKER_RUNTIME='prismora_worker.interp_engine_runtime:create_runtime'`;
see `CLOUD_RUNBOOK_INTERP_ENGINE.md` and `BRIDGE_C05_PREREGISTRATION.md`. It must pass that bridge
before any of its output is merged with Free Chat or HF-runtime corpora.
