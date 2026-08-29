# Prismora J-Lens Lab — 0.2.1 release-candidate state

Date: 2026-08-29
Base lineage: WorkFix `a39ebf45`

## Software gate

- 171/171 automated tests pass.
- Five external Fable/Cowork regression contracts are integrated under `tests/` and pass.
- Filesystem confinement, observed revision provenance, live-chat post-transform hashing, locked preregistration integrity, baseline identity/immutability, GPU execution locking, top-1 tie handling, truncated-top-k entropy naming, public bundle privacy, and source/package web parity are covered by code/tests.

## Historical provenance

`BUILD_MANIFEST.json` and `BASELINE_MANIFEST_SHA256.json` are retained as historical Build Week/pre-Build Week snapshots. They are not the manifest of this RC and contain an explicit `superseded_by` pointer to `RC_0.2.1_SHA256.json`.

## Typography decision — resolved

The author chose the original UI typography: **Spectral / Albert Sans / Spline Sans Mono**. The CSS now declares local `@font-face` sources and keeps system fallbacks only as graceful degradation. `FINALISER_POLICES_ET_RELEASE.command` vendors the exact OFL font assets from a pinned `google/fonts` commit, verifies their Git blob hashes, mirrors them into the packaged web tree, regenerates the RC manifest, and emits the tag-ready ZIP.

## External smoke gates still required

- one live Neuronpedia smoke run if provider access is part of the release claim;
- target-GPU numerical CUDA/J-Lens validation if the GPU runtime is part of the release claim;
- git tag/push/public release only after the author explicitly approves publication.
