from __future__ import annotations

import json
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Iterable

from .canonical import atomic_write_bytes, atomic_write_json, canonical_json_bytes, read_json, sha256_bytes, sha256_json
from .identifiers import validate_identifier
from .preregistration import verify_locked_spec
from .schema import validate
from .timeutil import utc_now_iso


class LabStore:
    """Small filesystem store with immutable raw artifacts and versioned JSON records."""

    def __init__(self, root: Path):
        self.root = root
        self.experiments_dir = root / "experiments"
        self.models_path = root / "model-registry.json"
        self.claims_dir = root / "claims"
        self.root.mkdir(parents=True, exist_ok=True)
        self.experiments_dir.mkdir(parents=True, exist_ok=True)
        self.claims_dir.mkdir(parents=True, exist_ok=True)
        if not self.models_path.exists():
            atomic_write_json(self.models_path, {"schema": "prismora.model-registry/v1", "models": []})

    def experiment_dir(self, experiment_id: str) -> Path:
        return self.experiments_dir / validate_identifier(experiment_id, "experiment")

    def experiment_path(self, experiment_id: str) -> Path:
        return self.experiment_dir(experiment_id) / "spec.json"

    def save_experiment(self, spec: dict[str, Any]) -> Path:
        validate("experiment", spec)
        path = self.experiment_path(spec["experiment_id"])
        path.parent.mkdir(parents=True, exist_ok=True)
        incoming_locked = spec.get("preregistration", {}).get("status") == "locked"
        if incoming_locked and not verify_locked_spec(spec):
            raise ValueError("Locked experiment hash does not match the document.")
        if path.exists():
            existing = read_json(path)
            validate("experiment", existing)
            if existing.get("preregistration", {}).get("status") == "locked":
                if not verify_locked_spec(existing):
                    raise ValueError("Stored locked experiment hash does not match the document.")
                if canonical_json_bytes(existing) != canonical_json_bytes(spec):
                    raise FileExistsError(
                        "Locked experiment is immutable. Use a new experiment_id or a documented amendment."
                    )
                return path
        atomic_write_json(path, spec)
        return path

    def get_experiment(self, experiment_id: str) -> dict[str, Any]:
        path = self.experiment_path(experiment_id)
        if not path.exists():
            raise FileNotFoundError(experiment_id)
        spec = read_json(path)
        validate("experiment", spec)
        if spec.get("preregistration", {}).get("status") == "locked" and not verify_locked_spec(spec):
            raise ValueError("Stored locked experiment hash does not match the document.")
        return spec

    def list_experiments(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for path in sorted(self.experiments_dir.glob("*/spec.json")):
            try:
                spec = read_json(path)
            except (OSError, json.JSONDecodeError):
                continue
            records.append(
                {
                    "experiment_id": spec.get("experiment_id"),
                    "title": spec.get("title"),
                    "status": spec.get("preregistration", {}).get("status", "draft"),
                    "spec_sha256": spec.get("preregistration", {}).get("spec_sha256"),
                    "tags": spec.get("tags", []),
                    "run_count": len(list((path.parent / "runs").glob("*/artifact.json"))) if (path.parent / "runs").exists() else 0,
                }
            )
        return records

    def _confined(self, path: Path) -> Path:
        resolved = path.resolve()
        root = self.root.resolve()
        if resolved == root or root not in resolved.parents:
            raise ValueError(f"Storage path escapes store root: {path}")
        return path

    def run_dir(self, experiment_id: str, run_id: str) -> Path:
        path = self.experiment_dir(experiment_id) / "runs" / validate_identifier(run_id, "run")
        return self._confined(path)

    def write_raw_bytes(self, experiment_id: str, run_id: str, raw_bytes: bytes) -> dict[str, Any]:
        """Write exact response bytes once. Existing different bytes are rejected."""
        if not isinstance(raw_bytes, (bytes, bytearray)):
            raise TypeError("raw_bytes must be bytes")
        exact_bytes = bytes(raw_bytes)
        raw_hash = sha256_bytes(exact_bytes)
        path = self.run_dir(experiment_id, run_id) / "raw.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            existing = path.read_bytes()
            if existing != exact_bytes:
                raise FileExistsError(f"Immutable raw already exists with different bytes: {path}")
        else:
            try:
                atomic_write_bytes(path, exact_bytes, overwrite=False)
            except FileExistsError:
                if path.read_bytes() != exact_bytes:
                    raise FileExistsError(f"Immutable raw already exists with different bytes: {path}") from None
        return {
            "path": path,
            "relative_path": str(path.relative_to(self.root)),
            "sha256": raw_hash,
            "byte_length": len(exact_bytes),
        }

    def write_raw(self, experiment_id: str, run_id: str, raw_value: dict[str, Any]) -> dict[str, Any]:
        """Compatibility wrapper for locally generated/imported JSON values."""
        return self.write_raw_bytes(experiment_id, run_id, canonical_json_bytes(raw_value))

    def save_run(self, artifact: dict[str, Any]) -> Path:
        self.verify_run_document(artifact, verify_raw_if_present=True)
        path = self.run_dir(artifact["experiment_id"], artifact["run_id"]) / "artifact.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            if canonical_json_bytes(read_json(path)) == canonical_json_bytes(artifact):
                return path
            raise FileExistsError(f"Immutable run artifact already exists: {path}")
        atomic_write_json(path, artifact, overwrite=False)
        return path

    def verify_run_document(self, artifact: dict[str, Any], *, verify_raw_if_present: bool) -> None:
        validate("run", artifact)
        validate_identifier(artifact.get("experiment_id"), "experiment")
        validate_identifier(artifact.get("run_id"), "run")
        provenance = artifact["provenance"]
        if provenance.get("request_sha256") != sha256_json(artifact["request"]):
            raise ValueError("Run artifact request_sha256 does not match request.")
        result_identity = {
            "meta": artifact["result"]["meta"],
            "tokens": artifact["result"]["tokens"],
            "done": artifact["result"]["done"],
        }
        if provenance.get("canonical_result_sha256") != sha256_json(result_identity):
            raise ValueError("Run artifact canonical_result_sha256 does not match result.")
        relative = Path(str(artifact["raw"]["relative_path"]))
        raw_path = (self.root / relative).resolve()
        root = self.root.resolve()
        if raw_path == root or root not in raw_path.parents:
            raise ValueError("Run artifact raw.relative_path escapes the store root.")
        if verify_raw_if_present and raw_path.exists():
            raw_bytes = raw_path.read_bytes()
            if provenance.get("raw_sha256") != sha256_bytes(raw_bytes):
                raise ValueError("Run artifact raw_sha256 does not match stored raw bytes.")
            if artifact["raw"].get("byte_length") != len(raw_bytes):
                raise ValueError("Run artifact raw.byte_length does not match stored raw bytes.")

    def commit_run(self, artifact: dict[str, Any], raw_bytes: bytes) -> Path:
        """Atomically publish an immutable raw/artifact pair as one run directory."""
        exact_raw = bytes(raw_bytes)
        self.verify_run_document(artifact, verify_raw_if_present=False)
        final_dir = self.run_dir(artifact["experiment_id"], artifact["run_id"])
        expected_raw = final_dir / "raw.json"
        expected_relative = str(expected_raw.relative_to(self.root))
        if artifact["raw"]["relative_path"] != expected_relative:
            raise ValueError("Run artifact raw.relative_path does not match its run identity.")
        if artifact["provenance"]["raw_sha256"] != sha256_bytes(exact_raw):
            raise ValueError("Run artifact raw_sha256 does not match supplied raw bytes.")
        if artifact["raw"].get("byte_length") != len(exact_raw):
            raise ValueError("Run artifact raw.byte_length does not match supplied raw bytes.")

        runs_dir = final_dir.parent
        runs_dir.mkdir(parents=True, exist_ok=True)
        if final_dir.exists():
            existing_raw = final_dir / "raw.json"
            existing_artifact = final_dir / "artifact.json"
            if (
                existing_raw.exists()
                and existing_artifact.exists()
                and existing_raw.read_bytes() == exact_raw
                and canonical_json_bytes(read_json(existing_artifact)) == canonical_json_bytes(artifact)
            ):
                return existing_artifact
            raise FileExistsError(f"Immutable run already exists: {final_dir}")

        stage = Path(tempfile.mkdtemp(prefix=".run-stage-", dir=runs_dir))
        try:
            atomic_write_bytes(stage / "raw.json", exact_raw, overwrite=False)
            atomic_write_json(stage / "artifact.json", artifact, overwrite=False)
            try:
                stage_fd = os.open(stage, os.O_RDONLY)
            except OSError:
                stage_fd = None
            if stage_fd is not None:
                try:
                    os.fsync(stage_fd)
                finally:
                    os.close(stage_fd)
            try:
                os.rename(stage, final_dir)
            except OSError:
                if final_dir.exists():
                    raise FileExistsError(f"Immutable run already exists: {final_dir}") from None
                raise
            return final_dir / "artifact.json"
        finally:
            if stage.exists():
                shutil.rmtree(stage)

    def get_run(self, run_id: str, experiment_id: str | None = None) -> dict[str, Any]:
        validate_identifier(run_id, "run")
        candidates: Iterable[Path]
        if experiment_id:
            candidates = [self.run_dir(experiment_id, run_id) / "artifact.json"]
        else:
            candidates = self.experiments_dir.glob(f"*/runs/{run_id}/artifact.json")
        for path in candidates:
            if path.exists():
                artifact = read_json(path)
                self.verify_run_document(artifact, verify_raw_if_present=True)
                return artifact
        raise FileNotFoundError(run_id)

    def list_runs(self, experiment_id: str | None = None) -> list[dict[str, Any]]:
        if experiment_id:
            paths = self.experiment_dir(experiment_id).glob("runs/*/artifact.json")
        else:
            paths = self.experiments_dir.glob("*/runs/*/artifact.json")
        records: list[dict[str, Any]] = []
        for path in sorted(paths):
            try:
                artifact = read_json(path)
            except (OSError, json.JSONDecodeError):
                continue
            result = artifact.get("result", {})
            tokens = result.get("tokens", [])
            records.append(
                {
                    "run_id": artifact.get("run_id"),
                    "experiment_id": artifact.get("experiment_id"),
                    "status": artifact.get("status"),
                    "backend": artifact.get("request", {}).get("backend"),
                    "model_alias": artifact.get("request", {}).get("model", {}).get("alias"),
                    "model_id": artifact.get("request", {}).get("model", {}).get("model_id"),
                    "prompt_id": artifact.get("request", {}).get("prompt_id"),
                    "factors": artifact.get("request", {}).get("factors", {}),
                    "repeat": artifact.get("request", {}).get("repeat"),
                    "created_at": artifact.get("provenance", {}).get("created_at"),
                    "canonical_result_sha256": artifact.get("provenance", {}).get("canonical_result_sha256"),
                    "execution_request_sha256": artifact.get("provenance", {}).get("execution_request_sha256"),
                    "independent_observation": artifact.get("quality", {}).get("independent_observation"),
                    "duplicate_of": artifact.get("quality", {}).get("duplicate_of"),
                    "token_count": len(tokens),
                    "generated_token_count": sum(1 for token in tokens if token.get("is_generated")),
                }
            )
        return records

    def find_duplicate(
        self,
        canonical_result_sha256: str,
        *,
        execution_request_sha256: str,
        exclude_run_id: str | None = None,
    ) -> str | None:
        for row in self.list_runs():
            if row.get("run_id") == exclude_run_id:
                continue
            if (
                row.get("canonical_result_sha256") == canonical_result_sha256
                and row.get("execution_request_sha256") == execution_request_sha256
            ):
                return str(row["run_id"])
        return None

    def get_models(self) -> dict[str, Any]:
        return read_json(self.models_path)

    def save_models(self, registry: dict[str, Any]) -> None:
        if not isinstance(registry.get("models"), list):
            raise ValueError("model registry must contain models[]")
        registry = dict(registry)
        registry.setdefault("schema", "prismora.model-registry/v1")
        atomic_write_json(self.models_path, registry)

    def claim_path(self, claim_id: str) -> Path:
        return self.claims_dir / f"{validate_identifier(claim_id, 'claim')}.json"

    def save_claim(self, claim: dict[str, Any]) -> Path:
        validate("claim", claim)
        path = self.claim_path(claim["claim_id"])
        atomic_write_json(path, claim)
        return path

    def list_claims(self, experiment_id: str | None = None) -> list[dict[str, Any]]:
        claims: list[dict[str, Any]] = []
        for path in sorted(self.claims_dir.glob("*.json")):
            try:
                claim = read_json(path)
            except (OSError, json.JSONDecodeError):
                continue
            if experiment_id and claim.get("experiment_id") != experiment_id:
                continue
            claims.append(claim)
        return claims

    def save_derived(self, experiment_id: str, category: str, record_id: str, value: dict[str, Any]) -> Path:
        safe_category = category.replace("/", "_").replace("..", "_")
        safe_id = record_id.replace("/", "_").replace("..", "_")
        path = self._confined(self.experiment_dir(experiment_id) / "derived" / safe_category / f"{safe_id}.json")
        if path.exists():
            existing = read_json(path)
            if canonical_json_bytes(existing) == canonical_json_bytes(value):
                return path
            raise FileExistsError(f"Derived record already exists with different content: {path}")
        atomic_write_json(path, value, overwrite=False)
        return path

    def build_bundle(self, experiment_id: str) -> Path:
        spec = self.get_experiment(experiment_id)
        exp_dir = self.experiment_dir(experiment_id)
        bundle_dir = exp_dir / "bundles"
        bundle_dir.mkdir(parents=True, exist_ok=True)
        stamp = utc_now_iso().replace(":", "-")
        destination = bundle_dir / f"{experiment_id}-{stamp}.zip"
        manifest: list[dict[str, Any]] = []
        candidates = [self.experiment_path(experiment_id)]
        excluded_live_chat_runs: list[str] = []
        for artifact_path in sorted((exp_dir / "runs").glob("*/artifact.json")):
            try:
                artifact = read_json(artifact_path)
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(artifact.get("derived", {}).get("live_chat"), dict):
                excluded_live_chat_runs.append(str(artifact.get("run_id") or artifact_path.parent.name))
                continue
            candidates.append(artifact_path)
            raw_path = artifact_path.parent / "raw.json"
            if raw_path.exists():
                candidates.append(raw_path)
        candidates.extend(sorted((exp_dir / "derived").glob("**/*.json")))
        for claim in self.list_claims(experiment_id):
            candidates.append(self.claim_path(claim["claim_id"]))
        with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in candidates:
                if not path.exists():
                    continue
                data = path.read_bytes()
                arcname = str(path.relative_to(self.root))
                archive.writestr(arcname, data)
                manifest.append({"path": arcname, "sha256": sha256_bytes(data), "bytes": len(data)})
            manifest_value = {
                "schema": "prismora.bundle-manifest/v1",
                "experiment_id": experiment_id,
                "created_at": utc_now_iso(),
                "preregistration_sha256": spec.get("preregistration", {}).get("spec_sha256"),
                "privacy": {
                    "policy": "public-default",
                    "excluded_live_chat_runs": excluded_live_chat_runs,
                    "note": "Live-chat artifacts and raws are excluded from public bundles by default.",
                },
                "files": manifest,
            }
            archive.writestr("MANIFEST.json", json.dumps(manifest_value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        return destination
