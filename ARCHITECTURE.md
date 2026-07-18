# Architecture

```text
ExperimentSpec v2
      │ validate / lock / SHA-256
      ▼
Matrix planner ──────────────► deterministic PlannedRun requests
      │
      ├── Mock backend
      ├── Neuronpedia adapter
      └── HTTP GPU worker adapter
            ├── mock runtime
            ├── supplied HF + jlens readout runtime
            └── private causal/fitting runtime plugin
                    │
                    ▼
 exact backend/source response bytes
        + parsed {meta,tokens,done}
                    │ immutable write
                    ▼
              RunArtifact v2
                    │
      ┌─────────────┼───────────────┐
      ▼             ▼               ▼
  Inspector      Analyses       Claim ledger
  cockpit v1     comparisons     graded claims
                baselines
                strict bridge
```

## Separation of responsibilities

- **Control plane:** protocols, secrets, planning, storage, claims and UI.
- **Execution backend:** one request in, one raw result out. It never edits a protocol.
- **Worker runtime:** owns model, tokenizer, lens, hooks and GPU precision.
- **Derived analyses:** immutable source artifacts in; versioned outputs out.
- **Claims:** human-authored statements linked to evidence and limitations.

## Backend capability negotiation

Every backend returns `prismora.backend-capabilities/v1`. The UI can display or
disable functionality according to declared readouts, interventions, forced
tokens, fitting and limits. The capability record does not prove correctness;
it only makes unsupported operations explicit.

## Run identities

A planned run ID contains a readable prefix and the first 12 hex characters of
a SHA-256 over the experiment ID and complete planned request. The full request
hash is preserved in `RunArtifact.provenance.request_sha256`.

The canonical result hash covers `{meta,tokens,done}`. Duplicate marking requires
both this hash and an identical executable-request hash (backend, model identity,
prompt/chat, generation, readout and intervention). Human labels and repeat
ordinals are excluded from the executable hash. This avoids collapsing identical
outputs from different models or prompts. It still does not infer whether a
remote server used a cache or repeated a physical forward pass.

`raw_sha256` covers the exact HTTP/source bytes. The parsed result is stored
separately so normalization never rewrites the evidence file.
