# Known limitations — v0.2.0

1. **No live Neuronpedia call was performed during the build.** The adapter and tests target the July 2026 documented request/response contract through a mocked HTTP transport.
2. **The worker defaults to synthetic data.** An optional readout-only HuggingFace + Anthropic `jlens` runtime is supplied, but it was not numerically validated on CUDA during this build. It rejects interventions and lens fitting.
3. **Execution is synchronous and intentionally capped.** The control plane runs at most `PRISMORA_MAX_RUNS_PER_REQUEST` observations per HTTP request. A durable distributed queue is a later milestone.
4. **Filesystem storage is single-node.** It is reliable for a local lab or one persistent control-plane volume, not concurrent multi-writer clusters.
5. **No user authentication.** Bind the control plane to localhost or protect it behind an authenticated reverse proxy. Worker bearer-token support is minimal, not a full identity system.
6. **No automatic cloud provisioning or billing integration.** The worker contract is vendor-neutral, but users provision/stop GPU machines themselves in v0.2.
7. **No lens fitting implementation.** `fit_lens` is a declared worker capability reserved for a future pinned runtime. The supplied real runtime only applies a pre-fitted lens.
8. **No semantic family classifier is bundled.** Exact token comparisons are available; semantic families remain preregistered experiment metadata until a versioned classifier is added.
9. **Generated-token ordinal alignment is simple.** Comparison Studio warns when output lengths differ; it does not yet provide dynamic semantic alignment.
10. **The top-1 baseline is descriptive.** It must not be interpreted as direct evidence of pretraining fossils, memories or model intent.
11. **Causal Lab builds and executes interventions but does not classify task-level strategy changes.** Outcome classifiers and random-direction controls must be defined by each experiment.
12. **The original cockpit HTML file is not copied from the File Library.** This release provides a new inspector plus a `cockpit.json` v1 compatibility endpoint based on the documented contract.
13. **Legacy matching relies on filenames containing `test_id`.** Ambiguous matches are reported and preserved in the import report; they should be resolved before publication.
