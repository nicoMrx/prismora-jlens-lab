from __future__ import annotations

import copy
import json
import platform
from typing import Any, Callable

from . import __version__
from .canonical import canonical_json_bytes, sha256_bytes, sha256_json
from .coverage import derive_coverage
from .schema import validate
from .store import LabStore
from .timeutil import utc_now_iso


def execution_request_identity(request: dict[str, Any]) -> dict[str, Any]:
    """Fields that reach or materially configure the inference backend.

    Human labels such as prompt_id, factor names and repeat ordinals are
    excluded so byte-identical results from the same executable condition can
    be recognized without collapsing identical text from different models or
    settings.
    """
    model = request.get("model", {})
    model_identity = {
        key: model.get(key)
        for key in (
            "model_id",
            "revision",
            "tokenizer_revision",
            "lens_id",
            "lens_revision",
            "precision",
            "quantization",
        )
        if key in model
    }
    identity: dict[str, Any] = {
        "backend": request.get("backend"),
        "model": model_identity,
        "generation": request.get("generation", {}),
        "readout": request.get("readout", {}),
        "intervention": request.get("intervention"),
    }
    if "prompt" in request:
        identity["prompt"] = request["prompt"]
    if "chat" in request:
        identity["chat"] = request["chat"]
    return identity


class RawShapeError(ValueError):
    pass


def validate_raw_shape(raw: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    for key in ("meta", "tokens", "done"):
        if key not in raw:
            raise RawShapeError(f"Raw result is missing {key!r}.")
    if not isinstance(raw["meta"], dict) or not isinstance(raw["done"], dict) or not isinstance(raw["tokens"], list):
        raise RawShapeError("Raw result must contain meta object, tokens array, and done object.")
    meta = raw["meta"]
    layers_by_type = meta.get("layers_by_type")
    if not isinstance(layers_by_type, dict):
        warnings.append("meta.layers_by_type is missing; layer indexes cannot be treated as actual layer numbers safely.")
    types = meta.get("types", [])
    for token in raw["tokens"]:
        if not isinstance(token, dict):
            raise RawShapeError("Every token must be an object.")
        for required in ("position", "token", "id", "is_generated", "results"):
            if required not in token:
                raise RawShapeError(f"Token is missing {required!r}.")
        result_types = {item.get("type") for item in token.get("results", []) if isinstance(item, dict)}
        missing = set(types) - result_types
        if missing:
            warnings.append(f"Position {token.get('position')} lacks result types: {sorted(missing)}")
    if meta.get("mock"):
        warnings.append("Synthetic mock data: valid for interface/pipeline testing only.")
    return sorted(set(warnings))


def create_run_artifact(
    *,
    store: LabStore,
    experiment_id: str,
    run_id: str,
    request: dict[str, Any],
    raw: dict[str, Any],
    raw_format: str,
    raw_bytes: bytes | None = None,
    raw_content_type: str = "application/json",
    backend_environment: dict[str, Any] | None = None,
    artifact_transform: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    warnings = validate_raw_shape(raw)
    exact_raw = bytes(raw_bytes) if raw_bytes is not None else canonical_json_bytes(raw)
    if raw_bytes is not None and ("json" in raw_content_type.lower() or "json" in raw_format.lower()):
        try:
            parsed = json.loads(exact_raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RawShapeError("raw_bytes is declared as JSON but cannot be parsed.") from exc
        parsed_result = parsed.get("result") if isinstance(parsed, dict) and isinstance(parsed.get("result"), dict) else parsed
        if not isinstance(parsed_result, dict) or sha256_json(parsed_result) != sha256_json(raw):
            raise RawShapeError("Parsed raw_bytes does not match the raw object supplied for normalization.")

    raw_path = store.run_dir(experiment_id, run_id) / "raw.json"
    raw_info = {
        "relative_path": str(raw_path.relative_to(store.root)),
        "sha256": sha256_bytes(exact_raw),
        "byte_length": len(exact_raw),
    }
    execution_request_hash = sha256_json(execution_request_identity(request))
    model = request.get("model", {})
    raw_meta = raw.get("meta", {}) if isinstance(raw.get("meta"), dict) else {}

    def observed_or_declared(*keys: str, declared: Any = None) -> Any:
        for key in keys:
            value = raw_meta.get(key)
            if value not in (None, ""):
                return value
        return declared

    observed_revisions = {
        "model_revision": observed_or_declared("model_revision", "revision", declared=model.get("revision")),
        "tokenizer_revision": observed_or_declared("tokenizer_revision", declared=model.get("tokenizer_revision")),
        "lens_id": observed_or_declared("lens_id", declared=model.get("lens_id")),
        "lens_revision": observed_or_declared("lens_revision", declared=model.get("lens_revision")),
    }
    artifact: dict[str, Any] = {
        "schema": "prismora.run/v2",
        "run_id": run_id,
        "experiment_id": experiment_id,
        "status": "ok",
        "request": copy.deepcopy(request),
        "provenance": {
            "created_at": utc_now_iso(),
            "backend": request.get("backend", "unknown"),
            "request_sha256": sha256_json(request),
            "execution_request_sha256": execution_request_hash,
            "raw_sha256": raw_info["sha256"],
            "canonical_result_sha256": "0" * 64,
            "code_version": __version__,
            "model_revision": observed_revisions["model_revision"],
            "tokenizer_revision": observed_revisions["tokenizer_revision"],
            "lens_id": observed_revisions["lens_id"],
            "lens_revision": observed_revisions["lens_revision"],
            "declared_revisions": {
                "model_revision": model.get("revision"),
                "tokenizer_revision": model.get("tokenizer_revision"),
                "lens_id": model.get("lens_id"),
                "lens_revision": model.get("lens_revision"),
            },
            "observed_revisions": copy.deepcopy(observed_revisions),
            "environment": {
                "python": platform.python_version(),
                "platform": platform.platform(),
                **(backend_environment or {}),
            },
        },
        "raw": {
            "relative_path": raw_info["relative_path"],
            "format": raw_format,
            "content_type": raw_content_type,
            "immutable": True,
            "byte_length": raw_info["byte_length"],
        },
        "result": {
            "meta": copy.deepcopy(raw["meta"]),
            "tokens": copy.deepcopy(raw["tokens"]),
            "done": copy.deepcopy(raw["done"]),
        },
        "coverage": derive_coverage(request, raw, backend_environment),
        "quality": {
            "independent_observation": True,
            "duplicate_of": None,
            "warnings": sorted(set(warnings)),
            "validation": "warning" if warnings else "passed",
            "prompt_copy_terms": [],
        },
        "error": None,
        "derived": {},
    }
    if artifact_transform is not None:
        artifact_transform(artifact)
    result_identity = {
        "meta": artifact["result"]["meta"],
        "tokens": artifact["result"]["tokens"],
        "done": artifact["result"]["done"],
    }
    canonical_result_hash = sha256_json(result_identity)
    artifact["provenance"]["canonical_result_sha256"] = canonical_result_hash
    duplicate_of = store.find_duplicate(
        canonical_result_hash,
        execution_request_sha256=execution_request_hash,
        exclude_run_id=run_id,
    )
    if duplicate_of:
        warning = "Canonical result duplicates a stored run; it is retained but does not count as an independent observation."
        artifact["quality"]["warnings"] = sorted(set([*artifact["quality"]["warnings"], warning]))
        artifact["quality"]["validation"] = "warning"
        artifact["quality"]["independent_observation"] = False
        artifact["quality"]["duplicate_of"] = duplicate_of
    validate("run", artifact)
    store.commit_run(artifact, exact_raw)
    return artifact
