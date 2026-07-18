from __future__ import annotations

import copy
from typing import Any

_FIELDS = (
    "source_tokens_total",
    "transmitted_tokens",
    "instrumented_tokens",
    "truncated_tokens",
    "source_messages_total",
    "transmitted_messages",
    "context_window_limit",
)


def _nonnull_int(value: Any, name: str) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int) or value < 0:
        raise ValueError(f"coverage.{name} must be a non-negative integer or null")
    return value


def validate_coverage(coverage: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(coverage, dict):
        raise ValueError("coverage must be an object")
    out = copy.deepcopy(coverage)
    for key in _FIELDS:
        out[key] = _nonnull_int(out.get(key), key)
    status = out.get("status", "unknown")
    if status not in {"complete", "partial", "unknown"}:
        raise ValueError("coverage.status must be complete, partial, or unknown")
    out["status"] = status
    for key in ("truncated_message_indices", "requested_layers", "captured_layers", "warnings"):
        value = out.get(key, [])
        if not isinstance(value, list):
            raise ValueError(f"coverage.{key} must be an array")
        out[key] = value
    for key in ("truncated_message_indices", "requested_layers", "captured_layers"):
        if any(not isinstance(item, int) or item < 0 for item in out[key]):
            raise ValueError(f"coverage.{key} values must be non-negative integers")
    if any(not isinstance(item, str) for item in out["warnings"]):
        raise ValueError("coverage.warnings values must be strings")
    return out


def derive_coverage(request: dict[str, Any], raw: dict[str, Any], backend_environment: dict[str, Any] | None = None) -> dict[str, Any]:
    backend_environment = backend_environment or {}
    reported = raw.get("coverage") or raw.get("meta", {}).get("coverage") or backend_environment.get("coverage")
    tokens = list(raw.get("tokens", []))
    layers_by_type = raw.get("meta", {}).get("layers_by_type", {}) if isinstance(raw.get("meta"), dict) else {}
    captured = sorted({int(layer) for layers in layers_by_type.values() if isinstance(layers, list) for layer in layers if isinstance(layer, int)})
    requested_raw = request.get("readout", {}).get("layers")
    requested = list(requested_raw) if isinstance(requested_raw, list) else captured
    if reported:
        cov = validate_coverage(reported)
    else:
        prompt_tokens = [t for t in tokens if not t.get("is_generated")]
        instrumented = sum(1 for t in tokens if t.get("results"))
        is_mock = raw.get("meta", {}).get("mock") or raw.get("done", {}).get("mock") or request.get("backend") == "mock"
        cov = {
            "source_tokens_total": len(prompt_tokens) if is_mock else None,
            "transmitted_tokens": len(prompt_tokens),
            "instrumented_tokens": instrumented,
            "truncated_tokens": 0 if is_mock else None,
            "source_messages_total": len(request.get("chat", [])) if "chat" in request else 1,
            "transmitted_messages": len(request.get("chat", [])) if "chat" in request else 1,
            "truncated_message_indices": [],
            "context_window_limit": None,
            "capture_mode": "full_returned_positions",
            "requested_layers": requested,
            "captured_layers": captured,
            "status": "complete" if is_mock else "partial",
            "warnings": [] if is_mock else ["The backend did not report the pre-truncation source-token total."],
        }
    return validate_coverage(cov)
