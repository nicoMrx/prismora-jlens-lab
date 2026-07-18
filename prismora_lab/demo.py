from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def verify_demo_manifest(demo_dir: Path) -> dict[str, Any]:
    manifest_path = demo_dir / "MANIFEST_SHA256.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    artifacts = []
    for item in manifest.get("items", []):
        rel = Path(item["path"])
        if rel.is_absolute() or ".." in rel.parts:
            raise ValueError(f"Unsafe demo manifest path: {item['path']}")
        data = (demo_dir / rel).read_bytes()
        if len(data) != item["bytes"]:
            raise ValueError(f"Demo manifest byte mismatch for {item['path']}")
        digest = hashlib.sha256(data).hexdigest()
        if digest != item["sha256"]:
            raise ValueError(f"Demo manifest SHA-256 mismatch for {item['path']}")
        artifact = json.loads(data.decode("utf-8"))
        artifacts.append(artifact)
    return {"manifest": manifest, "artifacts": artifacts}
