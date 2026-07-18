from __future__ import annotations

import hashlib
import math
import re
from typing import Any

from ..canonical import canonical_json_bytes
from .base import BackendResult, ExecutionBackend


_TOKEN_RE = re.compile(r"\s+|[^\s]+", re.UNICODE)


def _tokenize(text: str) -> list[str]:
    return [match.group(0) for match in _TOKEN_RE.finditer(text)] or [""]


def _token_id(token: str) -> int:
    return int(hashlib.sha256(token.encode("utf-8")).hexdigest()[:8], 16) % 150_000


def _request_text(request: dict[str, Any]) -> str:
    if "prompt" in request:
        return request["prompt"]
    return "\n".join(f"{m['role']}: {m['content']}" for m in request.get("chat", []))


def _completion_for(text: str) -> str:
    compact = text.replace(" ", "").lower()
    if "x^2" in compact or "x²" in compact:
        if "+6" in compact or "=6" in compact:
            return " Factor the polynomial: (x-2)(x-3)=0, so x=2 or x=3."
        return " Compute the discriminant, then apply the quadratic formula."
    if "photosynth" in compact:
        return " Plants convert light energy into chemical energy."
    return " Mock completion generated only to validate the laboratory workflow."


def _strategy_family(text: str) -> list[str]:
    compact = text.replace(" ", "").lower()
    if "x^2" in compact or "x²" in compact:
        if "+6" in compact or "=6" in compact:
            return [" factor", " factoring", " product", " roots", " 分解", " method", " equation", " solve"]
        return [" formula", " discriminant", " quadratic", " roots", " 公式", " calculate", " equation", " solve"]
    if "photosynth" in compact:
        return [" light", " energy", " plants", " glucose", " 光", " chlorophyll", " carbon", " oxygen"]
    return [" context", " response", " analysis", " model", " information", " answer", " process", " token"]


def _surface_family(surface: str, strategy: list[str]) -> list[str]:
    stripped = surface.strip()
    first = f" {stripped}" if stripped else " space"
    values = [first, *strategy]
    dedup: list[str] = []
    for value in values:
        if value not in dedup:
            dedup.append(value)
    while len(dedup) < 8:
        dedup.append(f" alt{len(dedup)}")
    return dedup[:8]


def _probabilities(seed: str, layer: int, rank_count: int) -> list[float]:
    digest = hashlib.sha256(f"{seed}:{layer}".encode()).digest()
    top = 0.18 + (digest[0] / 255) * 0.66
    decay = 0.48 + (digest[1] / 255) * 0.18
    values = [top * (decay**rank) for rank in range(rank_count)]
    total = sum(values)
    scale = min(0.98 / total, 1.0)
    return [round(value * scale, 4) for value in values]


class MockBackend(ExecutionBackend):
    backend_id = "mock"

    async def capabilities(self) -> dict[str, Any]:
        return {
            "schema": "prismora.backend-capabilities/v1",
            "backend_id": self.backend_id,
            "available": True,
            "mock": True,
            "readouts": ["LOGIT_LENS", "JACOBIAN_LENS"],
            "interventions": ["steer", "swap", "ablate"],
            "forced_tokens": True,
            "fit_lens": False,
            "supports_chat": True,
            "supports_completion": True,
            "models": ["mock/12-layer-lab-model"],
            "limits": {"max_new_tokens": 256, "max_top_k": 8, "max_input_tokens": 4096, "max_batch_runs": 64},
            "notes": ["Synthetic deterministic backend. It validates plumbing, not model cognition."],
        }

    async def run(self, request: dict[str, Any]) -> BackendResult:
        text = _request_text(request)
        completion = _completion_for(text)
        input_tokens = _tokenize(text)
        max_new = int(request.get("generation", {}).get("max_new_tokens", 32))
        completion_tokens = _tokenize(completion)[:max_new]
        all_tokens = input_tokens + completion_tokens
        prompt_len = len(input_tokens)
        lens_types = list(request.get("readout", {}).get("types", ["LOGIT_LENS", "JACOBIAN_LENS"]))
        top_k = min(int(request.get("readout", {}).get("top_k", 8)), 8)
        layers = list(range(12))
        strategy = _strategy_family(text)
        token_rows: list[dict[str, Any]] = []

        for position, surface in enumerate(all_tokens):
            results: list[dict[str, Any]] = []
            for lens in lens_types:
                top_tokens_by_layer: list[list[str]] = []
                top_probs_by_layer: list[list[float]] = []
                for layer in layers:
                    if layer <= 2:
                        candidates = [" a", " the", " and", " of", " in", " to", " s", " I"]
                    elif layer <= 8:
                        candidates = strategy
                    else:
                        candidates = _surface_family(surface, strategy)
                    if lens == "LOGIT_LENS" and layer >= 8:
                        candidates = _surface_family(surface, strategy)
                    candidates = candidates[:top_k]
                    probs = _probabilities(f"{request['model']['model_id']}:{position}:{surface}:{lens}", layer, len(candidates))
                    top_tokens_by_layer.append(candidates)
                    top_probs_by_layer.append(probs)
                results.append({"type": lens, "top_tokens": top_tokens_by_layer, "top_probs": top_probs_by_layer})
            token_rows.append(
                {
                    "kind": "token",
                    "position": position,
                    "token": surface,
                    "id": _token_id(surface),
                    "is_generated": position >= prompt_len,
                    "results": results,
                }
            )

        actual_completion = "".join(completion_tokens)
        value = {
            "meta": {
                "kind": "meta",
                "model": request["model"]["model_id"],
                "types": lens_types,
                "layers_by_type": {lens: layers for lens in lens_types},
                "top_n": top_k,
                "prompt_len": prompt_len,
                "num_completion_tokens": len(completion_tokens),
                "temperature": request.get("generation", {}).get("temperature", 0),
                "prepend_bos": request.get("generation", {}).get("prepend_bos", True),
                "reuse_len": 0,
                "backend": "mock",
                "mock": True,
            },
            "tokens": token_rows,
            "done": {
                "kind": "done",
                "seq_len": len(all_tokens),
                "prompt_len": prompt_len,
                "vocab_size": 150_000,
                "completion": actual_completion,
                "mock": True,
            },
        }
        return BackendResult(value=value, raw_bytes=canonical_json_bytes(value))

    def raw_format(self) -> str:
        return "mock-json"
