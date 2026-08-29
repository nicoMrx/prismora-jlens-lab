# Changelog

## 0.2.1 — 2026-08-13

- Reconstructed the six-source distribution into one installable project tree.
- Hardened storage identifiers, immutable run publication and locked protocols.
- Bound raw bytes, normalized results and stored hashes with regression tests.
- Revalidated matrix bindings and complete-coverage arithmetic.
- Corrected strict comparison semantics in Core and frontend.
- Transmitted declared Neuronpedia parameters and hardened the GPU worker.
- Packaged frontend and demo assets in wheels and source distributions.
- See `CORRECTION_REPORT.md` for scope limits and compatibility notes.

## 0.2.0 — 2026-07-14

- Added four versioned schemas.
- Added deterministic matrix planner and protocol lock.
- Added immutable raw/result store and duplicate detection.
- Added Neuronpedia, worker HTTP and mock backends.
- Added local web laboratory and cockpit v1 export.
- Added exact-token filter replay, empirical top-1 baseline and comparisons.
- Added intervention request builder and graded claim ledger.
- Added reproducibility bundles and SHA-256 manifests.
- Added provider-neutral worker plugin contract and runtime template.
- Added an optional readout-only HuggingFace + Anthropic `jlens` worker runtime pinned to the July 2026 reference release.
- Added strict public/private bridge comparison, GPU preflight and provider-neutral GPU container templates.
- Added automated end-to-end tests.

## Reliability additions before packaging

- Preserve exact HTTP/source raw bytes separately from normalized JSON.
- Scope duplicate observations by executable request identity, avoiding false collapse across different prompts/models/settings.
- Add v0.1 legacy campaign importer with chain reconstruction and source-byte SHA-256 verification.
- Add ready-to-review Neuronpedia campaign suite and a causal GPU-worker template.

## 0.2.1 RC — 2026-08-28

- hardened filesystem confinement and derived-record immutability;
- preserved declared and observed model/tokenizer/lens revisions;
- required `spec_sha256` for locked preregistrations;
- corrected baseline identity, top-1 tie handling and entropy naming;
- excluded live-chat evidence from public bundles by default;
- removed zero-byte font binaries and aligned release metadata;
- full suite: 166/166 passed.
