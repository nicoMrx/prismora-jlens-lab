import hashlib
import json
from pathlib import Path

from fastapi.testclient import TestClient

from prismora_lab.api.app import create_app
from prismora_lab.config import Settings
from prismora_lab.schema import validate
from prismora_lab.store import LabStore


ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "demo" / "showcase_2026"


def load(name):
    return json.loads((DEMO / name).read_text(encoding="utf-8"))


def git_blob_sha1(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def test_real_showcase_manifest_verifies_bytes_hashes_schema_and_nicomrx_signature():
    manifest = load("manifest.json")
    assert manifest["schema"] == "prismora.demo-library/v1"
    assert manifest["author"] == "NicoMrx" and manifest["signature"] == "NicoMrx"
    assert len(manifest["artifacts"]) == 4

    for item in manifest["artifacts"]:
        data = (DEMO / item["path"]).read_bytes()
        assert len(data) == item["bytes"]
        assert hashlib.sha256(data).hexdigest() == item["sha256"]
        assert git_blob_sha1(data) == item["git_blob_sha1"]
        artifact = json.loads(data)
        validate("run", artifact)
        assert artifact["run_id"] == item["run_id"]
        assert artifact["provenance"]["environment"]["curated_by"] == "NicoMrx"
        assert artifact["raw"]["immutable"] is True
        assert artifact["coverage"]["capture_mode"] == "curated_demo_subset"
        assert artifact["coverage"]["status"] == "partial"


def test_same_question_demo_is_identical_prompt_and_final_channel_normalized():
    qwen = load("showcase-same-question-qwen.json")
    gpt = load("showcase-same-question-gpt-oss-final.json")
    assert qwen["request"]["chat"][-1]["content"] == gpt["request"]["chat"][-1]["content"]
    assert qwen["request"]["generation"] == gpt["request"]["generation"]
    assert qwen["result"]["meta"]["prompt_len"] == 212
    assert gpt["result"]["meta"]["prompt_len"] == 262
    assert len(qwen["result"]["meta"]["requested_layers"] if "requested_layers" in qwen["result"]["meta"] else qwen["coverage"]["requested_layers"]) == 64
    assert len(gpt["coverage"]["requested_layers"]) == 24
    assert qwen["result"]["meta"]["default_channel"] == "final"
    assert gpt["result"]["meta"]["default_channel"] == "final"
    assert qwen["result"]["meta"]["channels"]["analysis"]["present"] is False
    assert gpt["result"]["meta"]["channels"]["analysis"]["present"] is True
    assert gpt["result"]["tokens"][0]["token"] == "Bonjour"


def test_meta_capture_preserves_full_observation_summary_and_controls():
    manifest = load("manifest.json")
    meta_card = next(card for card in manifest["cards"] if card["demo_id"] == "meta-capture")
    qwen = load("showcase-meta-qwen-observed.json")
    gpt = load("showcase-meta-gpt-oss-observed.json")
    qtrace = qwen["derived"]["concept_traces"]["meta"]
    gtrace = gpt["derived"]["concept_traces"]["meta"]

    assert qtrace == {
        "cells_top8": 1414,
        "positions": 70,
        "top1_cells": 242,
        "max_probability": 1.0,
        "top_hits": qtrace["top_hits"],
    }
    assert gtrace["cells_top8"] == 57
    assert gtrace["positions"] == 20
    assert gtrace["top1_cells"] == 2
    assert gtrace["max_probability"] == 0.2871
    assert max(hit["probability"] for hit in gtrace["top_hits"]) == 0.2871
    assert "méta" in qwen["result"]["done"]["completion"].lower()
    assert "méta" not in gpt["result"]["done"]["completion"].lower()
    assert meta_card["controls"]["qwen_branch_a"]["top1_cells"] == 0
    assert meta_card["controls"]["gpt_oss_branch_a"]["top1_cells"] == 0


def test_showcase_api_verifies_before_serving(tmp_path):
    client = TestClient(create_app(Settings(data_dir=tmp_path, neuronpedia_api_key=None, worker_url=None), store=LabStore(tmp_path)))
    response = client.get("/api/demo/showcase")
    assert response.status_code == 200
    payload = response.json()
    assert payload["signature"] == "NicoMrx"
    assert len(payload["verified_artifacts"]) == 4
    assert next(row for row in payload["verified_artifacts"] if row["run_id"] == "showcase-same-question-gpt-oss-final")["default_channel"] == "final"

    artifact = client.get("/api/demo/showcase/showcase-meta-gpt-oss-observed")
    assert artifact.status_code == 200
    assert artifact.json()["derived"]["concept_traces"]["meta"]["top1_cells"] == 2
    assert client.get("/api/demo/showcase/not-found").status_code == 404
