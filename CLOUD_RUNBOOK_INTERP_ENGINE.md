# Cloud runbook — first GPU session with the interp-engine runtime

Companion to `CLOUD_GPU_GUIDE.md` and `BRIDGE_C05_PREREGISTRATION.md`. Written 2026-09-02 from a static
review; every command is the intended one, none has been executed on a rented card yet. Expect to
edit this file during the first session and commit the corrected version.

## 0. Before renting anything

- `BRIDGE_C05_PREREGISTRATION.md` §1 has every `<commit>` filled in.
- The five replay exports are on the control-plane machine with their md5 recorded.
- interp-engine.org/sizer/Qwen/Qwen3.6-27B consulted with `resid_post`, all 64 layers, and the
  Jacobian-lens reservation enabled (do not add the lens memory by hand — `fit.py --jacobian-lens`
  already reserves `64 × 5120² × 4 B ≈ 6.7 GB` per card). Note the card/backend it proposes.
  As of the 1.5 release the sizer has **no verified row for any 27B model**; treat its Qwen3.6-27B
  figure as a prediction and keep 10 GB of margin.
- Card choice: one 80 GB card (A100/H100 class) for Qwen3.6-27B bf16; a 48 GB card (A40 class,
  verified in the engine's own table) is enough for GPT-OSS-20B (MXFP4) and for the density ladder.
- Provider budget ceiling and auto-stop rule written down (guide checklist).

## 1. Machine setup (one session, one model)

```bash
# Python 3.11–3.13 required by interp-engine
python3 -m venv ~/venv && source ~/venv/bin/activate
pip install --upgrade pip
pip install 'interp-engine[vllm]'            # Qwen3.6-27B
# pip install 'interp-engine[vllm,quant]'    # GPT-OSS-20B (MXFP4) — the [quant] extra is mandatory
pip install -r requirements-gpu.txt          # Prismora worker deps (fastapi, torch pin, jlens pin)
pip install -e .

# Pin everything through the environment (see GPU_RUNTIME_REFERENCE.md for the HF_/JLENS_ names)
export PRISMORA_WORKER_RUNTIME='prismora_worker.interp_engine_runtime:create_runtime'
export PRISMORA_HF_MODEL_ID='Qwen/Qwen3.6-27B'
export PRISMORA_HF_MODEL_REVISION='<commit>'
export PRISMORA_HF_TOKENIZER_REVISION='<commit>'
export PRISMORA_JLENS_NAME_OR_PATH='neuronpedia/jacobian-lens'
export PRISMORA_JLENS_FILENAME='qwen3.6-27b/jlens/Salesforce-wikitext/Qwen3.6-27B_jacobian_lens_n1000.pt'
export PRISMORA_JLENS_REVISION='<commit>'
export PRISMORA_JLENS_SHA256='1718c8c52dd8a9dad03738d4d625937c1fbba10be325b872ed446c7290fc11e1'
export PRISMORA_HF_DTYPE='bfloat16'
export PRISMORA_HF_MAX_INPUT_TOKENS=2048
export PRISMORA_HF_MAX_NEW_TOKENS=512
export PRISMORA_WORKER_TOKEN="$(python3 -c 'import secrets;print(secrets.token_hex(32))')"

# Path under test — change per bridge path (P1..P5)
export PRISMORA_IE_BACKEND='eager'            # eager | vllm | vllm-static
export PRISMORA_IE_CAPTURE_PATH='recompute'   # recompute | incremental
```

## 2. Preflight, then serve

```bash
prismora-worker-preflight             # env only
prismora-worker-preflight --load      # loads model + lens: this is where the SHA-256 and the
                                      # [64, 5120, 5120] shape check refuse a wrong checkpoint
python -m prismora_worker.app --host 0.0.0.0 --port 8100
curl -s -H "Authorization: Bearer $PRISMORA_WORKER_TOKEN" localhost:8100/v1/capabilities | python3 -m json.tool
```

`capabilities.runtime` must show `engine: interp-engine`, `engine_backend`, `compute_path`,
`lens_sha256`, `lens_shape`. If any is missing, the wrong runtime is loaded — stop.

## 3. The bridge, in order

For each path P1 → P5 (restart the worker between backends; one model per process):

1. Replay R1–R5 with generation disabled (`max_new_tokens: 0`, `readout.input_token_ids` from the
   export), `filter_nonword_tokens: false`, all `source_layers`, `top_k: 8`.
2. Same, `filter_nonword_tokens: true`.
3. P5 only: generation enabled, T=0, `seed: 0`, same prompt as the export; check the generated IDs
   against the archive **before** looking at any readout.
4. Record peak VRAM (`nvidia-smi --query-gpu=memory.used --format=csv -l 1 > vram.log &`), wall time
   per run, and the card's hourly price into the run's `meta` notes.

Every response is stored by the control plane as a `RunArtifact v2` with `raw_sha256`; nothing is
edited afterwards.

## 4. Compare

Comparison Studio → strict public/private bridge, P0 as reference, criteria of
`BRIDGE_C05_PREREGISTRATION.md` §4 applied verbatim. Output `tolerances_by_precision.json`, commit it,
write the backend decision in the claim ledger, update §4 of the preregistration with the outcome.

## 5. Shut down

Reproducibility bundle (exports, artefacts, `capabilities` JSON, `pip freeze`, `nvidia-smi -q` header,
this file as edited) copied off the machine **before** the instance is deleted. Then stop the card.

## Known unknowns to resolve in session

- Whether `interp_engine.load_model` on the vLLM backends honours a local snapshot path exactly as
  eager does (the runtime pre-downloads the pinned revision with `snapshot_download` for this reason).
- Whether `jlens.JacobianLens.transport` accepts CPU tensors from the vLLM `capture()` (returned on
  CPU) or needs `.to(device)` first — the eager path returns device tensors only with `detach=False`.
- Whether `decode_residuals` on vLLM returns the logits on CPU; the word mask is built per device
  lazily, so either works, but the first call is where it shows.
