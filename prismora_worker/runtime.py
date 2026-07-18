from __future__ import annotations

import importlib
import inspect
import os
from abc import ABC, abstractmethod
from typing import Any

from prismora_lab.backends.mock import MockBackend


class WorkerRuntime(ABC):
    runtime_id: str
    is_mock: bool = False

    @abstractmethod
    async def capabilities(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def run(self, request: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError


class MockRuntime(WorkerRuntime):
    runtime_id = "mock"
    is_mock = True

    async def capabilities(self) -> dict[str, Any]:
        return {
            "schema": "prismora.backend-capabilities/v1",
            "backend_id": "worker",
            "available": True,
            "mock": True,
            "readouts": ["LOGIT_LENS", "JACOBIAN_LENS"],
            "interventions": ["steer", "swap", "ablate"],
            "forced_tokens": True,
            "fit_lens": False,
            "supports_chat": True,
            "supports_completion": True,
            "models": ["mock/12-layer-lab-model"],
            "limits": {"max_new_tokens": 256, "max_top_k": 8, "max_input_tokens": 4096, "max_batch_runs": 1},
            "notes": [
                "Synthetic deterministic worker runtime.",
                "It validates deployment and UI contracts, not model cognition."
            ],
        }

    async def run(self, request: dict[str, Any]) -> dict[str, Any]:
        result = await MockBackend().run(request)
        raw = result.value
        raw["meta"]["backend"] = "worker"
        raw["meta"]["worker_runtime"] = self.runtime_id
        return raw


def load_runtime(spec: str | None = None) -> WorkerRuntime:
    """Load `mock` or an external `module.path:factory` runtime plugin."""
    spec = (spec or os.getenv("PRISMORA_WORKER_RUNTIME", "mock")).strip()
    if spec == "mock":
        return MockRuntime()
    if ":" not in spec:
        raise RuntimeError("PRISMORA_WORKER_RUNTIME must be 'mock' or 'module.path:factory'.")
    module_name, attribute = spec.split(":", 1)
    module = importlib.import_module(module_name)
    factory = getattr(module, attribute)
    runtime = factory()
    if inspect.isawaitable(runtime):
        raise RuntimeError("Runtime factory must be synchronous and return a WorkerRuntime-like object.")
    for method in ("capabilities", "run"):
        if not hasattr(runtime, method):
            raise RuntimeError(f"Runtime plugin lacks {method}().")
    return runtime
