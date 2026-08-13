from __future__ import annotations

import hashlib
import json
from pathlib import Path

from prismora_lab.canonical import sha256_json


ROOT = Path(__file__).resolve().parents[1]


def test_all_packaged_demo_artifacts_have_derivable_internal_hashes():
    artifacts = []
    for path in sorted((ROOT / "demo").glob("*/*.json")):
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("schema") == "prismora.run/v2":
            artifacts.append((path, value))
    assert len(artifacts) == 8
    for path, artifact in artifacts:
        assert artifact["provenance"]["request_sha256"] == sha256_json(artifact["request"]), path
        assert artifact["provenance"]["canonical_result_sha256"] == sha256_json(
            {key: artifact["result"][key] for key in ("meta", "tokens", "done")}
        ), path


def test_demo_manifests_match_repaired_artifact_bytes():
    for manifest_path, key in (
        (ROOT / "demo" / "build_week_2026" / "MANIFEST_SHA256.json", "items"),
        (ROOT / "demo" / "showcase_2026" / "manifest.json", "artifacts"),
    ):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for row in manifest[key]:
            data = (manifest_path.parent / Path(row["path"]).name).read_bytes()
            assert row["bytes"] == len(data)
            assert row["sha256"] == hashlib.sha256(data).hexdigest()
