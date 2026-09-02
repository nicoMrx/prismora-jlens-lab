# Prismora cloud/GPU C05 preparation status

Date: 2026-09-02
State: **STATIC / CONTRACT READY — NOT CUDA VALIDATED**

Prepared before renting GPU time:
- interp-engine runtime behind the existing worker contract;
- explicit `eager`, `vllm`, `vllm-static` engine metadata;
- explicit `recompute` vs `incremental` capture path;
- model/tokenizer snapshots pinned locally by revision;
- lens SHA-256 tied to the same local snapshot used for loading;
- optional explicit expected lens shape gate (`PRISMORA_JLENS_EXPECTED_SHAPE`);
- C05 bridge preregistration and cloud runbook;
- preflight refuses runs while `<commit>` / `<x.y.z>` placeholders remain.

Not claimed here:
- real CUDA/model load;
- numerical parity across runtimes;
- vLLM local-snapshot compatibility;
- jlens transport/logit device compatibility.
