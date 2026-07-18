from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


_SCHEMA_FILES = {
    "experiment": "experiment-spec-v2.schema.json",
    "run": "run-artifact-v2.schema.json",
    "capabilities": "backend-capabilities-v1.schema.json",
    "claim": "claim-record-v1.schema.json",
}


class SchemaValidationError(ValueError):
    def __init__(self, kind: str, errors: list[str]):
        self.kind = kind
        self.errors = errors
        super().__init__(f"{kind} schema validation failed: " + "; ".join(errors[:5]))


def schema_root() -> Path:
    source_root = Path(__file__).resolve().parents[1] / "schemas"
    if source_root.exists():
        return source_root
    return Path(__file__).resolve().parent / "assets" / "schemas"


@lru_cache(maxsize=None)
def load_schema(kind: str) -> dict[str, Any]:
    try:
        filename = _SCHEMA_FILES[kind]
    except KeyError as exc:
        raise KeyError(f"Unknown schema kind: {kind}") from exc
    with (schema_root() / filename).open("r", encoding="utf-8") as handle:
        return json.load(handle)


@lru_cache(maxsize=None)
def validator(kind: str) -> Draft202012Validator:
    return Draft202012Validator(load_schema(kind), format_checker=FormatChecker())


def validate(kind: str, value: Any) -> None:
    found = sorted(validator(kind).iter_errors(value), key=lambda err: list(err.absolute_path))
    if not found:
        return
    messages: list[str] = []
    for error in found:
        path = ".".join(str(part) for part in error.absolute_path) or "$"
        messages.append(f"{path}: {error.message}")
    raise SchemaValidationError(kind, messages)


def validation_report(kind: str, value: Any) -> dict[str, Any]:
    try:
        validate(kind, value)
    except SchemaValidationError as exc:
        return {"ok": False, "kind": kind, "errors": exc.errors}
    return {"ok": True, "kind": kind, "errors": []}
