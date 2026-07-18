# Validation report — v0.2.0

Build date: 2026-07-14

## Automated tests

```text
20 passed
```

Covered paths:

- all example ExperimentSpec documents validate and expand;
- canonical JSON and SHA-256 identities;
- deterministic run IDs and factor bindings;
- documented Neuronpedia buffered payload mapping;
- steer/swap field mapping;
- mocked Neuronpedia HTTP response and API-key header;
- immutable raw storage;
- executable-condition-scoped duplicate detection and non-independence marking;
- cockpit v1 compatibility export;
- exact-token filter replay generation;
- empirical top-1 baseline provenance;
- complete FastAPI mock campaign, lock, plan, run, inspect, compare and bundle;
- locked protocol edit rejection;
- worker capability and run contract;
- optional HuggingFace/J-Lens runtime configuration and Unicode filter helpers;
- strict public/private bridge equivalence and declared probability tolerance;
- non-destructive GPU worker preflight report.

## Additional smoke checks

- CLI validation: passed.
- CLI deterministic planning: passed, 3 mock runs.
- CLI execution and evidence bundle: passed.
- JavaScript syntax check with Node: passed.
- Local Uvicorn launch, `/api/health` and root interface fetch: passed.
- Wheel build: passed.
- Wheel installation into an isolated target: passed.
- Installed-package access to bundled schemas, examples and web assets: passed.

## Not validated in this environment

- live Neuronpedia authentication or inference;
- current server-side model availability/quotas;
- numerical execution of the supplied open-weight GPU/J-Lens runtime;
- public/private numerical bridge equivalence;
- provider billing, preemption and automatic GPU shutdown.

## Added integrity coverage

- exact HTTP/source-byte archival rather than parsed JSON reserialization;
- duplicate scoping by executable request identity;
- legacy `protocol.csv + raw/` import, including multi-turn chain reconstruction;
- validation and expansion of every campaign catalog example.
