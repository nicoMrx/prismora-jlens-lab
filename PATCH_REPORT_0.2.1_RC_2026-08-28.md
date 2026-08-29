# Prismora J-Lens Lab — patch report 0.2.1 RC

Date: 2026-08-28
Base: WorkFix `a39ebf45` (`prismora-dev`, tag `prismora-0.2.1-audit-fixed`)
Scope: finishing/repair only. No architecture or design rewrite.

## Fixed in this RC pass

1. **Filesystem confinement** — storage paths are resolved and required to remain under the store root in addition to identifier allow-list validation.
2. **Revision provenance** — model/tokenizer/lens revisions observed in raw metadata take precedence for the effective provenance fields; declared and observed revision blocks are both retained.
3. **Locked preregistration integrity** — JSON schema now requires a non-null SHA-256 when `preregistration.status == locked`.
4. **Baseline identity** — `max_tokens_per_layer` is part of the baseline identity and serialized result; different truncation settings no longer share a baseline ID.
5. **Derived-record immutability** — an existing derived record may be reused byte-equivalently but is not silently overwritten with different content.
6. **Top-1 ties** — equal-probability top candidates are treated as a tie set; permuting candidates within the same top tie no longer creates a false top-1 divergence.
7. **Entropy label** — cockpit output now names the value `topk_truncated_entropy`; it is not presented as full-distribution entropy.
8. **Public bundle privacy** — live-chat artifacts and their raw files are excluded from default public experiment bundles; exclusions are recorded in `MANIFEST.json`.
9. **Broken font payloads** — six zero-byte WOFF2 placeholders were removed. CSS now relies on local/system fallback stacks and does not fetch remote fonts. Existing OFL text files are retained as historical attribution material.
10. **Release metadata** — `CITATION.cff` aligned to version 0.2.1 and 2026-08-28; RC documentation updated.

## Regression coverage added

`tests/test_release_hardening_021.py` covers:
- observed vs declared revision provenance;
- locked preregistration SHA requirement;
- baseline identity sensitivity to `max_tokens_per_layer`;
- derived-record no-overwrite behavior;
- top-1 tie permutation behavior;
- public bundle exclusion of live-chat data.

## Validation

- Full pytest collection: **166 tests**.
- Full pytest suite: **166/166 passed**.
- `git diff --check`: clean.
- Python compileall: passed.

## Historical material intentionally not rewritten

Historical Build Week manifests/reports remain historical evidence and are not silently rewritten to pretend they described this RC. A new RC SHA-256 manifest is generated separately.

## Still outside this RC validation

- live provider authentication/inference in this container;
- CUDA/J-Lens numerical validation on target GPU hardware;
- store/account publication steps.
