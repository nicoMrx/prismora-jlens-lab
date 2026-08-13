# Corrected source assembly

This tree is a reconstructed, corrected copy of the six audited Prismora source
archives. The original archives are not embedded or modified.

The assembly maps the source blocks as follows:

- Core → `prismora_lab/`
- Tests → `tests/`
- Worker → `prismora_worker/`
- Frontend → `web/` and the installable mirror `prismora_lab/assets/web/`
- Contracts/data → `schemas/`, `examples/`, `demo/` and packaged asset mirrors
- Documentation/build files → project root

macOS Finder metadata (`.DS_Store` and `__MACOSX`) is excluded because it is
not project data and is not consumed by any build or runtime path.

See `CORRECTION_REPORT.md` for the exact corrective scope, verification record,
compatibility notes, and deliberately open audit findings.
