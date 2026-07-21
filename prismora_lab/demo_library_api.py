from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from fastapi import HTTPException


def _demo_dir(package_root: Path) -> Path:
    source = package_root / "demo" / "showcase_2026"
    if source.exists():
        return source
    packaged = Path(__file__).resolve().parent / "assets" / "demo" / "showcase_2026"
    if packaged.exists():
        return packaged
    raise FileNotFoundError("Real Neuronpedia showcase is not packaged.")


def _load_manifest(package_root: Path) -> tuple[Path, dict[str, Any]]:
    root = _demo_dir(package_root)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema") != "prismora.demo-library/v1":
        raise ValueError("Invalid demo-library manifest schema.")
    if manifest.get("signature") != "NicoMrx":
        raise ValueError("Demo-library signature is not NicoMrx.")
    return root, manifest


def _artifact_entry(manifest: dict[str, Any], run_id: str) -> dict[str, Any]:
    for item in manifest.get("artifacts", []):
        if item.get("run_id") == run_id:
            return item
    raise FileNotFoundError(run_id)


def _verified_artifact(root: Path, item: dict[str, Any]) -> dict[str, Any]:
    path = (root / Path(str(item["path"])).name).resolve()
    if path.parent != root.resolve() or not path.exists():
        raise FileNotFoundError(str(item.get("path")))
    data = path.read_bytes()
    if len(data) != int(item["bytes"]):
        raise ValueError(f"Demo byte mismatch for {path.name}.")
    if hashlib.sha256(data).hexdigest() != item["sha256"]:
        raise ValueError(f"Demo SHA-256 mismatch for {path.name}.")
    artifact = json.loads(data)
    if artifact.get("schema") != "prismora.run/v2" or artifact.get("run_id") != item.get("run_id"):
        raise ValueError(f"Invalid demo artifact {path.name}.")
    if artifact.get("provenance", {}).get("environment", {}).get("curated_by") != "NicoMrx":
        raise ValueError(f"Demo artifact {path.name} is not signed by NicoMrx.")
    return artifact


def mount_demo_library_routes(app: Any, package_root: Path) -> None:
    @app.get("/api/demo/showcase")
    async def demo_showcase_manifest() -> dict[str, Any]:
        try:
            root, manifest = _load_manifest(package_root)
            verified = []
            for item in manifest.get("artifacts", []):
                artifact = _verified_artifact(root, item)
                verified.append(
                    {
                        "run_id": artifact["run_id"],
                        "model_id": artifact.get("request", {}).get("model", {}).get("model_id"),
                        "source_sha256": artifact.get("provenance", {}).get("raw_sha256"),
                        "default_channel": artifact.get("result", {}).get("meta", {}).get("default_channel", "final"),
                    }
                )
            return {**manifest, "verified_artifacts": verified}
        except Exception as exc:
            status = 404 if isinstance(exc, FileNotFoundError) else 500
            raise HTTPException(status_code=status, detail=str(exc)) from exc

    @app.get("/api/demo/showcase/{run_id}")
    async def demo_showcase_artifact(run_id: str) -> dict[str, Any]:
        try:
            root, manifest = _load_manifest(package_root)
            return _verified_artifact(root, _artifact_entry(manifest, run_id))
        except Exception as exc:
            status = 404 if isinstance(exc, FileNotFoundError) else 500
            raise HTTPException(status_code=status, detail=str(exc)) from exc
