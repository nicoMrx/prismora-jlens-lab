"""Template for a real open-weight/J-Lens worker runtime.

Copy this module into a private deployment package, pin every dependency and
checkpoint, then set:

    PRISMORA_WORKER_RUNTIME=my_runtime:create_runtime

Do not label a runtime scientific-ready until it passes a public/private bridge
validation on identical model weights, tokenizer, lens, token IDs and precision.
"""
from __future__ import annotations

from typing import Any

from .runtime import WorkerRuntime


class PinnedJLensRuntime(WorkerRuntime):
    runtime_id = "replace-with-runtime-and-commit"
    is_mock = False

    def __init__(self) -> None:
        # Load exactly one pinned model/tokenizer/lens per worker process.
        # Record immutable revisions and reject implicit quantization changes.
        self.model_id = "replace-with-model-id"

    async def capabilities(self) -> dict[str, Any]:
        return {
            "schema": "prismora.backend-capabilities/v1",
            "backend_id": "worker",
            "available": True,
            "mock": False,
            "readouts": ["LOGIT_LENS", "JACOBIAN_LENS"],
            "interventions": ["steer", "swap", "ablate"],
            "forced_tokens": True,
            "fit_lens": False,
            "supports_chat": True,
            "supports_completion": True,
            "models": [self.model_id],
            "limits": {"max_new_tokens": 512, "max_top_k": 16, "max_input_tokens": 32768, "max_batch_runs": 1},
            "notes": ["Replace this template with a pinned implementation."],
        }

    async def run(self, request: dict[str, Any]) -> dict[str, Any]:
        # Required return contract:
        # {
        #   "meta": {
        #     "model": exact_model_id,
        #     "types": [...],
        #     "layers_by_type": {lens: [actual layer numbers]},
        #     "top_n": int,
        #     "prompt_len": int,
        #     "model_revision": "...",
        #     "tokenizer_revision": "...",
        #     "lens_revision": "...",
        #     "precision": "bf16",
        #     "quantization": null
        #   },
        #   "tokens": [{position, token, id, is_generated, results: [...]}],
        #   "done": {seq_len, prompt_len, completion, ...}
        # }
        raise NotImplementedError("Implement the pinned J-Lens runtime here.")


def create_runtime() -> WorkerRuntime:
    return PinnedJLensRuntime()
