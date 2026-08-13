from __future__ import annotations

import copy
from typing import Any

_FIELDS = (
    "source_tokens_total",
    "transmitted_tokens",
    "instrumented_tokens",
    "instrumented_generated_tokens",
    "truncated_tokens",
    "source_messages_total",
    "transmitted_messages",
    "context_window_limit",
)


def _nonnull_int(value: Any, name: str) -> int | None:
    if value is None:
        return None
    # ``bool`` is a subclass of ``int`` in Python, but accepting true/false as
    # token counts would make malformed coverage records appear valid.
    if type(value) is not int or value < 0:
        raise ValueError(f"coverage.{name} must be a non-negative integer or null")
    return value


def validate_coverage(coverage: dict[str, Any]) -> dict[str, Any]:
    """Validate explicit context-coverage semantics.

    transmitted_tokens and instrumented_tokens refer only to non-generated
    input/context positions sent to the backend. Generated positions with
    readout results are tracked separately in instrumented_generated_tokens.
    """
    if not isinstance(coverage, dict):
        raise ValueError("coverage must be an object")
    out = copy.deepcopy(coverage)
    for key in _FIELDS:
        out[key] = _nonnull_int(out.get(key), key)
    if out["transmitted_tokens"] is not None and out["instrumented_tokens"] is not None:
        if out["instrumented_tokens"] > out["transmitted_tokens"]:
            raise ValueError("coverage.instrumented_tokens cannot exceed coverage.transmitted_tokens")
    status = out.get("status", "unknown")
    if status not in {"complete", "partial", "unknown"}:
        raise ValueError("coverage.status must be complete, partial, or unknown")
    if status == "complete" and (
        out["source_tokens_total"] is None or out["transmitted_tokens"] is None or out["instrumented_tokens"] is None or out["truncated_tokens"] is None
    ):
        raise ValueError("coverage.status complete requires known source, transmitted, instrumented, and truncated token counts")
    if status == "complete":
        if out["source_tokens_total"] != out["transmitted_tokens"] + out["truncated_tokens"]:
            raise ValueError(
                "coverage.status complete requires source_tokens_total == transmitted_tokens + truncated_tokens"
            )
        if out["instrumented_tokens"] != out["transmitted_tokens"]:
            raise ValueError(
                "coverage.status complete requires every transmitted context token to be instrumented"
            )
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
        return validate_coverage(reported)

    prompt_tokens = [t for t in tokens if not t.get("is_generated")]
    generated_tokens = [t for t in tokens if t.get("is_generated")]
    def has_measurements(token: dict[str, Any]) -> bool:
        return any(
            isinstance(result, dict)
            and any(isinstance(row, list) and row for row in result.get("top_tokens", []))
            for result in token.get("results", [])
        )

    instrumented_context = sum(1 for t in prompt_tokens if has_measurements(t))
    instrumented_generated = sum(1 for t in generated_tokens if has_measurements(t))
    is_mock = raw.get("meta", {}).get("mock") or raw.get("done", {}).get("mock") or request.get("backend") == "mock"
    cov = {
        "source_tokens_total": len(prompt_tokens) if is_mock else None,
        "transmitted_tokens": len(prompt_tokens),
        "instrumented_tokens": instrumented_context,
        "instrumented_generated_tokens": instrumented_generated,
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
