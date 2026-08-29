# Validation report — v0.2.1 RC2 pre-typography decision

Build date: 2026-08-29
Base: WorkFix `a39ebf45` + Pepper release hardening + Fable regression suite

## Automated tests

```text
171 collected
171 passed
```

The complete suite includes the pre-existing Prismora tests, the 0.2.1 release-hardening tests, and the five Fable/Cowork regression contracts covering traversal, observed-vs-declared revision provenance, live-chat post-transform hashing, baseline identity, and top-1 tie handling.

## Static/build checks

- `python3 -m compileall prismora_lab prismora_worker`: passed.
- source/package frontend trees remain byte-identical.
- source/package schema trees remain byte-identical.
- historical Build Week / pre-Build Week manifests are preserved and explicitly marked as superseded by the RC manifest.
- `.pytest_cache`, `.git`, virtual environments and other local caches are excluded from the RC manifest/package.

## Not validated in this container

- live Neuronpedia authentication or inference;
- current provider-side availability/quotas;
- numerical CUDA/open-weight J-Lens execution on target GPU hardware;
- external publication/tag/push.

## Open author decision before final release candidate

Typography policy remains to be chosen: embed the intended OFL fonts (Spectral, Albert Sans, Spline Sans Mono), or keep the current system-font fallback and document the visual deviation from the Build Week/video typography.
