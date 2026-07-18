from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .canonical import atomic_write_json, sha256_bytes, sha256_json
from .matrix import expand_experiment
from .normalize import create_run_artifact
from .schema import validate
from .store import LabStore
from .timeutil import utc_now_iso


class LegacyImportError(ValueError):
    pass


_TRUE = {"1", "true", "yes", "y", "on"}
_FALSE = {"0", "false", "no", "n", "off", ""}


def _bool(value: Any, *, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in _TRUE:
        return True
    if text in _FALSE:
        return False
    raise LegacyImportError(f"Invalid boolean value: {value!r}")


def _int(value: Any, *, default: int) -> int:
    text = str(value or "").strip()
    return int(text) if text else default


def _float(value: Any, *, default: float) -> float:
    text = str(value or "").strip()
    return float(text) if text else default


def _safe_id(value: str, *, max_length: int = 80) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-._") or "legacy"
    if not slug[0].isalnum():
        slug = "x-" + slug
    if len(slug) <= max_length:
        return slug
    return slug[: max_length - 13].rstrip("-._") + "-" + sha256_bytes(value.encode("utf-8"))[:12]


def _completion(raw: dict[str, Any]) -> str:
    done = raw.get("done")
    if isinstance(done, dict) and isinstance(done.get("completion"), str):
        return done["completion"]
    messages = raw.get("messages")
    if isinstance(messages, list):
        for message in reversed(messages):
            if isinstance(message, dict) and message.get("role") == "assistant" and isinstance(message.get("content"), str):
                return message["content"]
    tokens = raw.get("tokens")
    if isinstance(tokens, list):
        return "".join(
            str(token.get("token", ""))
            for token in tokens
            if isinstance(token, dict) and token.get("is_generated")
        )
    return ""


def normalize_legacy_raw(value: dict[str, Any]) -> dict[str, Any]:
    """Map API or manual v1 exports to the common meta/tokens/done result shape."""
    if not isinstance(value, dict):
        raise LegacyImportError("Legacy raw root must be an object")
    if all(key in value for key in ("meta", "tokens", "done")):
        return {"meta": value["meta"], "tokens": value["tokens"], "done": value["done"]}
    if "meta" not in value or "tokens" not in value:
        raise LegacyImportError("Legacy raw lacks meta/tokens")
    tokens = value["tokens"]
    if not isinstance(tokens, list):
        raise LegacyImportError("Legacy raw tokens must be an array")
    prompt_len = sum(1 for token in tokens if isinstance(token, dict) and not token.get("is_generated"))
    completion = _completion(value)
    done = {
        "kind": "done",
        "seq_len": len(tokens),
        "prompt_len": prompt_len,
        "completion": completion,
        "legacy_manual_envelope": True,
    }
    return {"meta": value["meta"], "tokens": tokens, "done": done}


@dataclass(slots=True)
class LegacyRecord:
    row: dict[str, str]
    raw_path: Path
    raw_bytes: bytes
    raw_value: dict[str, Any]
    result: dict[str, Any]
    prompt_spec: dict[str, Any]
    model_id: str
    generation: dict[str, Any]
    readout: dict[str, Any]


_REQUIRED_COLUMNS = {
    "test_id",
    "conversation",
    "turn",
    "mode",
    "language",
    "model_id",
    "prompt",
    "input_kind",
    "filter_nonword",
    "top_n",
    "temperature",
    "num_completion_tokens",
    "prepend_bos",
    "enable_thinking",
}


def _index_raw_files(raw_dir: Path) -> list[Path]:
    files = sorted(path for path in raw_dir.rglob("*.json") if path.is_file())
    if not files:
        raise LegacyImportError(f"No JSON raws found under {raw_dir}")
    return files


def _find_raw(raw_files: list[Path], test_id: str) -> tuple[Path | None, list[Path]]:
    exact = [path for path in raw_files if path.stem == test_id or path.stem.endswith("__" + test_id)]
    if len(exact) == 1:
        return exact[0], exact
    if exact:
        return exact[0], exact
    relaxed = [path for path in raw_files if test_id in path.stem]
    return (relaxed[0] if relaxed else None), relaxed


def _record_signature(record: LegacyRecord) -> str:
    return sha256_json(
        {
            "model_id": record.model_id,
            "generation": record.generation,
            "readout": record.readout,
        }
    )


def import_legacy_campaign(
    *,
    protocol_path: Path,
    raw_dir: Path,
    store: LabStore,
    experiment_prefix: str,
) -> dict[str, Any]:
    """Import v0.1 protocol.csv + raw JSON while preserving original bytes.

    Rows are split into reproducible ExperimentSpec groups whenever model or
    execution settings differ. Chain requests are reconstructed from stored
    assistant completions in protocol order. Missing chain turns break the
    remainder of that conversation rather than creating false partial context.
    """

    protocol_path = protocol_path.resolve()
    raw_dir = raw_dir.resolve()
    with protocol_path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        columns = set(reader.fieldnames or [])
        missing_columns = sorted(_REQUIRED_COLUMNS - columns)
        if missing_columns:
            raise LegacyImportError(f"protocol.csv lacks columns: {', '.join(missing_columns)}")
        rows = [dict(row) for row in reader]
    if not rows:
        raise LegacyImportError("protocol.csv contains no rows")

    raw_files = _index_raw_files(raw_dir)
    histories: dict[str, list[dict[str, str]]] = {}
    broken_conversations: set[str] = set()
    records: list[LegacyRecord] = []
    missing: list[dict[str, Any]] = []
    ambiguous: list[dict[str, Any]] = []

    for row_index, row in enumerate(rows, start=2):
        test_id = str(row.get("test_id", "")).strip()
        conversation = str(row.get("conversation", test_id)).strip() or test_id
        mode = str(row.get("mode", "fresh")).strip().lower()
        if mode == "chain" and conversation in broken_conversations:
            missing.append(
                {
                    "test_id": test_id,
                    "row": row_index,
                    "reason": "skipped because an earlier chain turn is missing",
                }
            )
            continue
        raw_path, candidates = _find_raw(raw_files, test_id)
        if not raw_path:
            missing.append({"test_id": test_id, "row": row_index, "reason": "raw not found"})
            if mode == "chain":
                broken_conversations.add(conversation)
            continue
        if len(candidates) > 1:
            ambiguous.append(
                {
                    "test_id": test_id,
                    "selected": str(raw_path),
                    "candidates": [str(path) for path in candidates],
                }
            )

        raw_bytes = raw_path.read_bytes()
        try:
            raw_value = json.loads(raw_bytes)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            missing.append({"test_id": test_id, "row": row_index, "reason": f"invalid JSON: {exc}"})
            if mode == "chain":
                broken_conversations.add(conversation)
            continue
        result = normalize_legacy_raw(raw_value)
        prompt_text = str(row.get("prompt", ""))
        input_kind = str(row.get("input_kind", "chat")).strip().lower()

        if mode == "chain":
            chat = [*histories.get(conversation, []), {"role": "user", "content": prompt_text}]
            prompt_spec: dict[str, Any] = {
                "prompt_id": _safe_id(test_id),
                "chat": chat,
                "metadata": {
                    "legacy_test_id": test_id,
                    "conversation": conversation,
                    "turn": _int(row.get("turn"), default=1),
                    "mode": mode,
                    "language": row.get("language", ""),
                    "raw_filename": raw_path.name,
                },
            }
            histories[conversation] = [*chat, {"role": "assistant", "content": _completion(result)}]
        elif input_kind == "completion":
            prompt_spec = {
                "prompt_id": _safe_id(test_id),
                "prompt": prompt_text,
                "metadata": {
                    "legacy_test_id": test_id,
                    "conversation": conversation,
                    "turn": _int(row.get("turn"), default=1),
                    "mode": mode,
                    "language": row.get("language", ""),
                    "raw_filename": raw_path.name,
                },
            }
        else:
            prompt_spec = {
                "prompt_id": _safe_id(test_id),
                "chat": [{"role": "user", "content": prompt_text}],
                "metadata": {
                    "legacy_test_id": test_id,
                    "conversation": conversation,
                    "turn": _int(row.get("turn"), default=1),
                    "mode": mode,
                    "language": row.get("language", ""),
                    "raw_filename": raw_path.name,
                },
            }

        meta = result.get("meta", {})
        model_id = str(row.get("model_id") or meta.get("model") or "unknown")
        types = meta.get("types")
        if not isinstance(types, list) or not types:
            types = ["LOGIT_LENS", "JACOBIAN_LENS"]
        generation = {
            "temperature": _float(row.get("temperature"), default=0.0),
            "max_new_tokens": _int(row.get("num_completion_tokens"), default=128),
            "seed": None,
            "prepend_bos": _bool(row.get("prepend_bos"), default=True),
            "enable_thinking": _bool(row.get("enable_thinking"), default=False),
            "frequency_penalty": 0,
        }
        readout = {
            "types": types,
            "top_k": _int(row.get("top_n"), default=int(meta.get("top_n", 8) or 8)),
            "filter_nonword_tokens": _bool(row.get("filter_nonword"), default=True),
            "exclude_first_n_positions": 0,
        }
        records.append(
            LegacyRecord(
                row=row,
                raw_path=raw_path,
                raw_bytes=raw_bytes,
                raw_value=raw_value,
                result=result,
                prompt_spec=prompt_spec,
                model_id=model_id,
                generation=generation,
                readout=readout,
            )
        )

    grouped: dict[str, list[LegacyRecord]] = defaultdict(list)
    for record in records:
        grouped[_record_signature(record)].append(record)

    experiment_summaries: list[dict[str, Any]] = []
    total_artifacts = 0
    for group_index, (signature, group) in enumerate(sorted(grouped.items()), start=1):
        first = group[0]
        model_slug = _safe_id(first.model_id.lower(), max_length=34).lower()
        experiment_id = _safe_id(
            f"{experiment_prefix}-{group_index:02d}-{model_slug}-{signature[:8]}",
            max_length=80,
        ).lower()
        aliases_seen: set[str] = set()
        prompts: list[dict[str, Any]] = []
        record_by_prompt_id: dict[str, LegacyRecord] = {}
        for record in group:
            prompt_spec = dict(record.prompt_spec)
            base_id = prompt_spec["prompt_id"]
            prompt_id = base_id
            suffix = 1
            while prompt_id in aliases_seen:
                suffix += 1
                prompt_id = _safe_id(f"{base_id}-{suffix}")
            aliases_seen.add(prompt_id)
            prompt_spec["prompt_id"] = prompt_id
            prompts.append(prompt_spec)
            record_by_prompt_id[prompt_id] = record

        spec: dict[str, Any] = {
            "schema": "prismora.experiment/v2",
            "experiment_id": experiment_id,
            "title": f"Legacy import: {first.model_id} ({group_index})",
            "description": (
                "Reconstructed from a Prismora J-Lens Lab v0.1 protocol.csv and original raw JSON. "
                "The protocol is historical, not retrospectively preregistered."
            ),
            "tags": ["legacy-import", "historical", "v0.1"],
            "hypothesis": {
                "primary": "Historical observations are imported without altering their raw evidence bytes.",
                "falsifiers": ["A stored raw SHA-256 differs from its source file SHA-256."],
                "exploratory": [],
            },
            "preregistration": {"status": "draft", "locked_at": None, "spec_sha256": None, "amendments": []},
            "models": [
                {
                    "alias": "LEGACY01",
                    "model_id": first.model_id,
                    "backend": "neuronpedia",
                    "blind_alias": "LEGACY01",
                    "organization": None,
                    "origin_region": None,
                    "model_type": "unknown",
                    "revision": None,
                    "tokenizer_revision": None,
                    "lens_id": "legacy Neuronpedia J-Lens export",
                    "lens_revision": None,
                    "precision": None,
                    "quantization": None,
                    "metadata": {"imported": True},
                }
            ],
            "prompts": prompts,
            "matrix": {"factors": {}, "bindings": {}, "repeats": 1},
            "generation": first.generation,
            "readout": first.readout,
            "intervention": None,
            "analysis": {
                "primary_metric": "legacy_import_integrity",
                "secondary_metrics": [],
                "exclusions": [],
                "compare_absolute_and_relative_depth": True,
                "semantic_families": {},
                "generated_positions_only": False,
                "presence_min_probability": 0.01,
                "notes": "No retrospective preregistration claim. Original row metadata remains in prompt metadata and artifact provenance.",
            },
            "stopping_rule": "Historical import only.",
            "metadata": {
                "legacy_protocol": str(protocol_path),
                "legacy_raw_dir": str(raw_dir),
                "legacy_settings_signature": signature,
                "imported_at": utc_now_iso(),
            },
        }
        validate("experiment", spec)
        store.save_experiment(spec)
        planned = {run.request["prompt_id"]: run for run in expand_experiment(spec)}
        artifacts = []
        for prompt_id, record in record_by_prompt_id.items():
            run = planned[prompt_id]
            artifact = create_run_artifact(
                store=store,
                experiment_id=experiment_id,
                run_id=run.run_id,
                request=run.request,
                raw=record.result,
                raw_format="imported-json",
                raw_bytes=record.raw_bytes,
                raw_content_type="application/json; source=legacy-file",
                backend_environment={
                    "legacy_protocol": str(protocol_path),
                    "legacy_raw_path": str(record.raw_path),
                    "legacy_raw_sha256": sha256_bytes(record.raw_bytes),
                    "legacy_test_id": record.row.get("test_id"),
                    "legacy_conversation": record.row.get("conversation"),
                    "legacy_turn": record.row.get("turn"),
                    "legacy_language": record.row.get("language"),
                },
            )
            artifacts.append(artifact["run_id"])
            total_artifacts += 1
        experiment_summaries.append(
            {
                "experiment_id": experiment_id,
                "model_id": first.model_id,
                "settings_signature": signature,
                "run_count": len(artifacts),
                "run_ids": artifacts,
            }
        )

    report = {
        "schema": "prismora.legacy-import-report/v1",
        "created_at": utc_now_iso(),
        "protocol_path": str(protocol_path),
        "raw_dir": str(raw_dir),
        "experiment_prefix": experiment_prefix,
        "rows": len(rows),
        "imported_records": len(records),
        "stored_artifacts": total_artifacts,
        "experiments": experiment_summaries,
        "missing": missing,
        "ambiguous_matches": ambiguous,
        "integrity_note": "Each artifact raw_sha256 is computed over the original source file bytes.",
    }
    imports_dir = store.root / "imports"
    imports_dir.mkdir(parents=True, exist_ok=True)
    report_path = imports_dir / f"{_safe_id(experiment_prefix.lower())}-{sha256_json(report)[:12]}.json"
    atomic_write_json(report_path, report)
    report["report_path"] = str(report_path)
    return report
