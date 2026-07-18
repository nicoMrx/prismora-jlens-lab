from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any, Iterable

from .canonical import atomic_write_bytes, atomic_write_json, canonical_json_bytes, read_json, sha256_bytes
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
        return self.experiments_dir / experiment_id

    def experiment_path(self, experiment_id: str) -> Path:
        return self.experiment_dir(experiment_id) / "spec.json"

    def save_experiment(self, spec: dict[str, Any]) -> Path:
        validate("experiment", spec)
        path = self.experiment_path(spec["experiment_id"])
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(path, spec)
        return path

    def get_experiment(self, experiment_id: str) -> dict[str, Any]:
        path = self.experiment_path(experiment_id)
        if not path.exists():
            raise FileNotFoundError(experiment_id)
        return read_json(path)

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

    def run_dir(self, experiment_id: str, run_id: str) -> Path:
        return self.experiment_dir(experiment_id) / "runs" / run_id

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
            atomic_write_bytes(path, exact_bytes, overwrite=False)
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
        validate("run", artifact)
        path = self.run_dir(artifact["experiment_id"], artifact["run_id"]) / "artifact.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(path, artifact)
        return path

    def get_run(self, run_id: str, experiment_id: str | None = None) -> dict[str, Any]:
        candidates: Iterable[Path]
        if experiment_id:
            candidates = [self.run_dir(experiment_id, run_id) / "artifact.json"]
        else:
            candidates = self.experiments_dir.glob(f"*/runs/{run_id}/artifact.json")
        for path in candidates:
            if path.exists():
                return read_json(path)
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
        return self.claims_dir / f"{claim_id}.json"

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
        path = self.experiment_dir(experiment_id) / "derived" / safe_category / f"{safe_id}.json"
        atomic_write_json(path, value)
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
        candidates.extend(sorted((exp_dir / "runs").glob("*/artifact.json")))
        candidates.extend(sorted((exp_dir / "runs").glob("*/raw.json")))
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
                "files": manifest,
            }
            archive.writestr("MANIFEST.json", json.dumps(manifest_value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        return destination
