#!/usr/bin/env python3
"""Recompute derivable Prismora artifact hashes and enclosing demo manifests.

This maintenance utility intentionally never changes ``raw_sha256``: that
value can only be verified from the exact source bytes referenced by the
artifact. It updates request/result hashes whose complete inputs are embedded
in the artifact itself, then refreshes manifest byte and file hashes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def write_preserving_style(path: Path, value: Any, *, pretty: bool) -> None:
    if pretty:
        text = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"
    else:
        text = json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    path.write_text(text, encoding="utf-8")


def repair_artifact(path: Path) -> None:
    original = path.read_text(encoding="utf-8")
    artifact = json.loads(original)
    if artifact.get("schema") != "prismora.run/v2":
        raise ValueError(f"Not a Prismora run artifact: {path}")
    artifact["provenance"]["request_sha256"] = sha256_json(artifact["request"])
    result = artifact["result"]
    artifact["provenance"]["canonical_result_sha256"] = sha256_json(
        {"meta": result["meta"], "tokens": result["tokens"], "done": result["done"]}
    )
    write_preserving_style(path, artifact, pretty=original.startswith("{\n"))


def git_blob_sha1(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()


def refresh_manifest(path: Path) -> None:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    rows = manifest.get("items") if isinstance(manifest.get("items"), list) else manifest.get("artifacts")
    if not isinstance(rows, list):
        raise ValueError(f"Unsupported demo manifest: {path}")
    for row in rows:
        artifact_path = path.parent / Path(str(row["path"])).name
        data = artifact_path.read_bytes()
        row["bytes"] = len(data)
        row["sha256"] = hashlib.sha256(data).hexdigest()
        if "git_blob_sha1" in row:
            row["git_blob_sha1"] = git_blob_sha1(data)
    write_preserving_style(path, manifest, pretty=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("demo_root", type=Path)
    args = parser.parse_args()
    artifacts = sorted(
        path
        for path in args.demo_root.glob("*/*.json")
        if path.name not in {"MANIFEST_SHA256.json", "manifest.json", "campaign_01.json"}
    )
    for path in artifacts:
        repair_artifact(path)
    for name in ("build_week_2026/MANIFEST_SHA256.json", "showcase_2026/manifest.json"):
        refresh_manifest(args.demo_root / name)


if __name__ == "__main__":
    main()
