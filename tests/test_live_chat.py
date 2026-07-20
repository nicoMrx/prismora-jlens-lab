from pathlib import Path

from fastapi.testclient import TestClient

from prismora_lab.api.app import create_app
from prismora_lab.backends.mock import MockBackend
from prismora_lab.config import Settings
from prismora_lab.store import LabStore


def make_app(tmp_path: Path):
    store = LabStore(tmp_path)
    app = create_app(
        Settings(data_dir=tmp_path, neuronpedia_api_key=None, worker_url=None),
        store=store,
        backends={"mock": MockBackend(), "neuronpedia": MockBackend()},
    )
    return app, store


def test_live_models_are_explicit_and_signed(tmp_path):
    app, _ = make_app(tmp_path)
    client = TestClient(app)
    response = client.get("/api/live/models")
    assert response.status_code == 200
    body = response.json()
    assert body["signature"] == "NicoMrx"
    assert body["defaults"]["temperature"] == 0
    assert body["defaults"]["top_k"] == 8
    assert {row["model_id"] for row in body["models"]} == {
        "qwen3.6-27b", "gpt-oss-20b", "gemma-3-12b"
    }


def test_live_chat_requires_a_successfully_tested_connection(tmp_path):
    app, _ = make_app(tmp_path)
    client = TestClient(app)
    response = client.post("/api/live/chat", json={"message": "Bonjour", "model_id": "qwen3.6-27b"})
    assert response.status_code == 409
    assert "successfully tested" in str(response.json()["detail"])


def test_live_chat_creates_reproducible_spec_raw_and_artifact(tmp_path):
    app, store = make_app(tmp_path)
    app.state.lab.session.neuronpedia_api_key = "session-secret-never-returned"
    app.state.lab.session.neuronpedia_connected = True
    app.state.lab.backends["neuronpedia"] = MockBackend()
    client = TestClient(app)

    response = client.post(
        "/api/live/chat",
        json={
            "message": "Explique la photosynthèse en une phrase.",
            "model_id": "qwen3.6-27b",
            "temperature": 0,
            "max_new_tokens": 32,
            "top_k": 8,
            "lens_types": ["JACOBIAN_LENS", "LOGIT_LENS"],
        },
    )
    assert response.status_code == 200, response.text
    artifact = response.json()
    assert artifact["schema"] == "prismora.run/v2"
    assert artifact["status"] == "ok"
    assert artifact["request"]["backend"] == "neuronpedia"
    assert artifact["request"]["model"]["model_id"] == "qwen3.6-27b"
    assert artifact["request"]["chat"][-1]["content"] == "Explique la photosynthèse en une phrase."
    assert artifact["raw"]["immutable"] is True
    assert artifact["derived"]["live_chat"]["signed_by"] == "NicoMrx"
    assert artifact["provenance"]["environment"]["signature"] == "NicoMrx"
    assert "session-secret-never-returned" not in response.text

    stored = store.get_run(artifact["run_id"], artifact["experiment_id"])
    assert stored["provenance"]["raw_sha256"] == artifact["provenance"]["raw_sha256"]
    raw_path = store.root / stored["raw"]["relative_path"]
    assert raw_path.exists() and raw_path.read_bytes()
    spec = store.get_experiment(artifact["experiment_id"])
    assert spec["metadata"]["signature"] == "NicoMrx"
    assert spec["preregistration"]["status"] == "draft"


def test_live_chat_rejects_unknown_model_and_invalid_limits(tmp_path):
    app, _ = make_app(tmp_path)
    app.state.lab.session.neuronpedia_api_key = "configured"
    app.state.lab.session.neuronpedia_connected = True
    client = TestClient(app)

    unknown = client.post("/api/live/chat", json={"message": "Bonjour", "model_id": "unknown-model"})
    assert unknown.status_code == 502
    assert "Unsupported live-chat model" in unknown.text

    invalid = client.post(
        "/api/live/chat",
        json={"message": "Bonjour", "model_id": "qwen3.6-27b", "max_new_tokens": 257},
    )
    assert invalid.status_code == 502
    assert "max_new_tokens must be in the range 1..256" in invalid.text
