# Validation report — Prismora J-Lens Lab v0.2.1

Validation date: 2026-08-29
Release base: WorkFix `a39ebf45` + Pepper release hardening + Fable regression suite + restored original OFL typography
Release commit: `0c1087b364bd7ea1627f2da630950e044e808f0c`
Release tag: `v0.2.1`

## Automated tests

```text
171 collected
171 passed
```

The complete suite includes the pre-existing Prismora tests, the 0.2.1 release-hardening tests, and the five Fable/Cowork regression contracts covering traversal, observed-vs-declared revision provenance, live-chat post-transform hashing, baseline identity, and top-1 tie handling.

## Static/build checks

- `python3 -m compileall -q prismora_lab prismora_worker`: passed.
- `git diff --check`: passed before the release commit.
- source/package frontend trees remain byte-identical.
- source/package schema trees remain byte-identical.
- historical Build Week / pre-Build Week manifests are preserved and explicitly marked as superseded by the 0.2.1 release manifest.
- `.pytest_cache`, `.git`, virtual environments, editable-install metadata and other local caches are excluded from the release manifest/package.

## Typography and packaging

The original interface typography is restored locally and vendored under the SIL Open Font License 1.1:

- Spectral;
- Albert Sans;
- Spline Sans Mono.

Font files and exact OFL license texts are sourced from the pinned `google/fonts` commit `ade3d1533e06b2b1462ffcde8e08b129627ca360`. The UI has no runtime font CDN/network dependency.

## Public release state

- GitHub release `Prismora J-Lens Lab 0.2.1` is published and marked **Latest**.
- annotated tag `v0.2.1` points to release commit `0c1087b364bd7ea1627f2da630950e044e808f0c`.
- `main` was fast-forwarded to the release commit and is the repository default branch.
- historical branch `build-week-2026` remains preserved separately at its contest snapshot.
- `RC_0.2.1_SHA256.json` records the reproducible release tree.

## Validation intentionally outside the software-release gate

The following remain environment- or hardware-specific validation steps and are not represented as having been validated by the automated release suite:

- live Neuronpedia authentication or provider-side inference;
- current provider-side availability or quotas;
- numerical CUDA/open-weight J-Lens execution on target GPU hardware.

These items do not alter the software-release status of v0.2.1; they belong to runtime/experimental validation.
