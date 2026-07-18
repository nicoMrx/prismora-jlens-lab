# Prismora J-Lens Lab v0.2.0

A local-first, backend-neutral laboratory for reproducible J-Lens experiments.
The same `ExperimentSpec v2` can target:

- the public Neuronpedia `/api/lens/prompt` workflow;
- a private or rented GPU through the Prismora worker HTTP contract;
- a deterministic synthetic backend for testing the laboratory itself.

This release is an **executable foundation**, not a finished causal GPU
runtime. The Neuronpedia adapter is implemented against the API contract
available in July 2026. It was not live-called while this package was built,
because no API key was available in the build environment. The worker defaults
to synthetic data, and an optional readout-only HuggingFace + Anthropic `jlens`
runtime is included for a pinned model, tokenizer and pre-fitted lens. Real CUDA
loading and numerical bridge equivalence still require validation on a GPU host.

## What is implemented

- `ExperimentSpec v2`, `RunArtifact v2`, backend-capability and claim schemas.
- Deterministic matrix expansion with stable run IDs.
- SHA-256 identities for requests, raw bytes, canonical results and locked protocols.
- Immutable exact response bytes: a stored raw cannot be silently overwritten or reserialized.
- Duplicate-result detection: duplicates remain archived but do not count as independent observations.
- Neuronpedia buffered-JSON adapter with prompt/chat, exact `inputTokenIds`, both lenses, filtering and steer/swap/ablate fields.
- Vendor-neutral HTTP GPU-worker adapter and plugin contract.
- Optional readout-only HuggingFace + Anthropic `jlens` runtime with exact-token replay, Jacobian/Logit read-outs and explicit filter identity.
- Local web interface with experiment editor, preregistration lock, model registry, campaign planner, fleet capabilities, run archive, heatmap, top-k inspector, exact filter replay, empirical baseline builder, causal request builder, comparison studio and claim ledger.
- Original Prismora cockpit v1 compatibility export.
- Strict public/private bridge mode comparing exact surface token IDs, actual layer lists, ranked top-k strings and probability deltas under an explicit tolerance.
- Reproducibility ZIPs containing specs, raws, artifacts, derived baselines, claims and a SHA-256 manifest.
- Import of the v0.1 `protocol.csv + raw/` corpus with exact-byte preservation and chain reconstruction.
- A deterministic mock backend so every interface and storage path can be tested without money, a key or a GPU.

## Install and start

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
python -m pip install -e ".[dev]"
python -m prismora_lab.cli serve
```

Open `http://127.0.0.1:8000`.

Run the test suite:

```bash
python -m pytest
```

### First complete flow without external services

1. Open **Experiments**.
2. Load `strategy_quadratic_mock.json`.
3. Save the draft, then lock it.
4. Open **Campaign builder**, build the plan and execute three runs.
5. Open **Run inspector** and **Comparison studio**.
6. Download the evidence bundle.

The mock backend is clearly tagged in every artifact. It is evidence about the
software pipeline only, never about a language model.

## Neuronpedia execution

Set the key on the server process, never in browser JavaScript:

```bash
export NEURONPEDIA_API_KEY='...'
python -m prismora_lab.cli serve
```

The adapter sends `stream: false`, parses `{meta, tokens, done}` for the normalized artifact, and archives the exact HTTP response bytes before any reserialization. Supported request mapping:

| ExperimentSpec field | Neuronpedia payload |
|---|---|
| `model.model_id` | `modelId` |
| `prompt` / `chat` | `prompt` / `chat` |
| `readout.types` | `type` |
| `readout.top_k` | `topN` |
| `generation.temperature` | `temperature` |
| `generation.max_new_tokens` | `numCompletionTokens` |
| `generation.prepend_bos` | `prependBos` |
| `generation.enable_thinking` | `enableThinking` |
| `readout.filter_nonword_tokens` | `filterNonWordTokens` |
| `readout.input_token_ids` | `inputTokenIds` |
| intervention source/layers/strength | `steerTokens` / `steerLayers` / `steerStrength` |
| ablation / swap | `steerAblate` / `swapToken` |

The adapter enforces the documented public limits of top-k ≤ 8 and generated
tokens ≤ 256. Model availability is still determined by Neuronpedia.

### Exact filter calibration

A generated run with `filter_nonword_tokens=true` and another independently
generated run with it set to false are not a clean matched pair. The output
sequence might differ.

The laboratory therefore provides **Create exact filter replay**:

1. Run a source condition once.
2. Select the source in **Baseline lab**.
3. Create a replay experiment.
4. Review and lock the generated spec.
5. Execute both conditions.

The replay spec feeds the complete stored token-ID sequence back through
`inputTokenIds`, sets generation to zero and changes only the filter binding.
The comparison mode `filter_effect` checks token-ID identity before computing
per-layer top-1 change rates and top-k Jaccard.

## Cloud GPU worker

Start the bundled contract worker:

```bash
python -m prismora_worker.app --host 127.0.0.1 --port 8100
```

It defaults to `PRISMORA_WORKER_RUNTIME=mock`. A real deployment supplies a
plugin factory:

```bash
export PRISMORA_WORKER_RUNTIME='my_pinned_runtime:create_runtime'
export PRISMORA_WORKER_TOKEN='long-random-secret'
python -m prismora_worker.app --host 0.0.0.0 --port 8100
```

The control plane points to it with:

```bash
export PRISMORA_WORKER_URL='https://your-protected-worker.example'
export PRISMORA_WORKER_TOKEN='long-random-secret'
```

For the supplied real readout path, install `requirements-gpu.txt` and set:

```bash
export PRISMORA_WORKER_RUNTIME='prismora_worker.hf_jlens_runtime:create_runtime'
```

Then provide the pinned model/lens variables documented in
`GPU_RUNTIME_REFERENCE.md`. Run `prismora-worker-preflight` before loading the
weights, and `prismora-worker-preflight --load` for an expensive startup check.
This path supports read-outs and exact token replay; it deliberately rejects
steering, swaps, ablations and lens fitting until those operations have a
separately tested runtime. `Dockerfile.gpu.reference` and
`docker-compose.gpu.reference.yml` provide a provider-neutral deployment shell.

See `CLOUD_GPU_GUIDE.md`, `GPU_RUNTIME_REFERENCE.md` and
`prismora_worker/runtime_template.py`. The worker contract is provider-neutral:
RunPod, Lambda, Vast, Scaleway, AWS, GCP, Azure or an on-premises machine can be
used if the endpoint is protected and the runtime returns the required shape.

## Data layout

```text
.prismora-data/
  model-registry.json
  claims/
    <claim_id>.json
  experiments/
    <experiment_id>/
      spec.json
      runs/
        <run_id>/
          raw.json          # immutable exact source/HTTP bytes
          artifact.json     # normalized RunArtifact v2
      derived/
        baselines/
          <baseline_id>.json
      bundles/
        <experiment>-<timestamp>.zip
```

## Core trust invariants

1. **Raw is never rewritten.** A conflicting second write fails.
2. **Request identity includes the complete request**, not only the final prompt.
3. **Duplicate output is not independent evidence.** It is linked to the first matching canonical result.
4. **Locked protocol is immutable through the API.** Amendments require a new ID or an explicit future amendment workflow.
5. **Actual layer numbers are preserved.** Relative depth is displayed as a coordinate, never as automatic equivalence.
6. **Filters, precision, quantization, tokenizer and lens revision are protocol/provenance variables.**
7. **Origin region is metadata.** Cross-model differences are not attributed to nationality without matched controls.
8. **The interface does not generate mental-state labels.** Claims live in a separate, graded ledger.
9. **A lexical change is not automatically a strategy change.** Causal experiments need task-level outcome measures and controls.
10. **Null and refuting results remain publishable artifacts.**

## Main API routes

```text
GET/POST  /api/experiments
POST      /api/experiments/{id}/lock
POST      /api/experiments/{id}/plan
POST      /api/runs/execute
GET       /api/runs/{run_id}
GET       /api/runs/{run_id}/cockpit
POST      /api/runs/{run_id}/make-filter-replay
POST      /api/runs/{run_id}/intervene
POST      /api/import/neuronpedia
POST      /api/baselines/build
POST      /api/compare              # agreement, filter_effect or strict bridge
GET/POST  /api/models
GET/POST  /api/claims
GET       /api/experiments/{id}/bundle
```

FastAPI also exposes interactive local API documentation at `/docs`.

## Command line

```bash
prismora-lab validate experiment examples/strategy_quadratic_01.json
prismora-lab plan examples/strategy_quadratic_mock.json
prismora-lab run examples/strategy_quadratic_mock.json --backend mock --limit 3
prismora-lab bundle strategy-quadratic-mock
prismora-lab import-legacy --protocol protocol.csv --raw-dir camp01/raw --experiment-prefix camp01
```

The legacy importer splits rows by model/execution settings, reconstructs chain
contexts from stored completions and verifies that every imported `raw_sha256`
is computed over the original file bytes. Historical imports remain drafts;
they are never relabeled as preregistered.

See `CAMPAIGN_CATALOG.md` for the ready-to-review API campaign suite.

## Scientific status

The software can preserve and compare observations. It cannot make an
observation causal by naming it causal. The claim ledger distinguishes:

`observation → replication → robustness → prediction → causality → generalization`

The strongest unfinished engineering steps are: validating the supplied pinned
readout runtime on CUDA; performing a public/private bridge test with identical
weights, tokenizer, lens, token IDs and precision; and implementing causal hooks
whose outcome is measured at the task level rather than by a changed word alone.


## Build Week 2026 submission layer

### Pre-existing project vs Build Week contribution

Prismora is an existing independent research project. The Build Week submission layer was implemented during the event with Codex and GPT-5.6. Pre-existing work includes ExperimentSpec v2, RunArtifact v2, the mock/Neuronpedia/worker contracts, immutable raw storage, campaign tools, Run Inspector, Comparison Studio, Claim Ledger, bridge checks, and the A/B Human Visualizer v0.2.1. Build Week adds explicit context coverage, deterministic Understand narratives with rule/evidence traces, bilingual EN/FR submission UI, and curated synthetic demo artifacts.

### Codex and GPT-5.6 workflow

Codex accelerated implementation by editing schemas, Python comparison facts, API endpoints, web assets, tests, and documentation in one auditable Git history. GPT-5.6/Codex contributed implementation support; the human product and scientific decisions were the boundary between evidence and interpretation, the refusal to infer unknown coverage, bilingual submission-path requirements, and the explicit caution that readout divergence is not semantic or causal proof. Runtime inference does not call GPT-5.6 unless a separate backend is explicitly configured.

### Local judge demo

Supported platform: local Python 3.11+ environment on macOS, Linux, or compatible containers.

```bash
python -m pip install -e ".[dev]"
python -m uvicorn prismora_lab.api.app:create_app --factory --reload
```

Open the local web app, import or execute mock runs, then use the Human Visualizer Understand card. Curated no-key/no-GPU sample data lives in `demo/build_week_2026/` with `MANIFEST_SHA256.json`; Pair A has identical generated surface with internal divergence at layer 40, and Pair B has a visible surface difference.

### Known limitations

Understand is rule-based and intentionally narrow: it reports measured coverage and readout facts, not cognition, bias, censorship, consciousness, or causality. Public bridge comparisons still use decoded top-k token strings where candidate token IDs are unavailable. Generated-token comparison is ordinal only and is labeled as such. Remember to obtain `/feedback` from the primary Codex thread for the Build Week submission.
