import json
from pathlib import Path

from fastapi.testclient import TestClient

from prismora_lab.api.app import create_app
from prismora_lab.backends.mock import MockBackend
from prismora_lab.campaigns import legacy_campaign_to_plan
from prismora_lab.config import Settings
from prismora_lab.store import LabStore


ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "demo" / "campaign_01_2026" / "campaign_01.json"


def legacy_campaign():
    return json.loads(DEMO.read_text(encoding="utf-8"))


def test_campaign_01_compiles_to_exact_29_conditions_and_87_runs():
    plan = legacy_campaign_to_plan(legacy_campaign(), author="NicoMrx")
    assert plan["schema"] == "prismora.campaign/v1"
    assert plan["author"] == "NicoMrx" and plan["signature"] == "NicoMrx"
    assert plan["condition_count"] == 29
    assert plan["run_count"] == 87
    assert plan["by_model"] == {"gemma-3-12b": 12, "qwen3.6-27b": 75}
    assert len(plan["specs"]) == 29
    gemma = [row for row in plan["conditions"] if row["model_id"] == "gemma-3-12b"]
    assert len(gemma) == 4
    assert all(row["input_kind"] == "completion" for row in gemma)
    assert all(row["max_new_tokens"] == 32 for row in gemma)
    assert sum(not row["filter_nonword_tokens"] for row in plan["conditions"]) == 2


def test_campaign_api_preview_save_lock_and_resumable_preflight(tmp_path):
    store = LabStore(tmp_path)
    backend = MockBackend()
    client = TestClient(
        create_app(
            Settings(data_dir=tmp_path, neuronpedia_api_key=None, worker_url=None),
            store=store,
            backends={"mock": backend, "neuronpedia": backend},
        )
    )
    payload = legacy_campaign()

    demo = client.get("/api/demo/campaign-01")
    assert demo.status_code == 200
    assert len(demo.json()["cells"]) == len(payload["cells"])

    preview = client.post("/api/campaigns/legacy/preview", json=payload)
    assert preview.status_code == 200
    assert preview.json()["condition_count"] == 29
    assert preview.json()["run_count"] == 87
    assert len(preview.json()["compiled_experiment_ids"]) == 29

    saved = client.post("/api/campaigns/legacy/save", json=payload)
    assert saved.status_code == 200
    assert saved.json()["planned_runs"] == 87
    assert saved.json()["completed_runs"] == 0
    assert saved.json()["signature"] == "NicoMrx"

    listed = client.get("/api/campaigns")
    assert listed.status_code == 200
    assert listed.json()["campaigns"][0]["campaign_id"] == "campaign-01"

    # GO/NO-GO: no lock and no batch execution before a successful preflight.
    assert client.post("/api/campaigns/campaign-01/lock", json={}).status_code == 409
    assert client.post("/api/campaigns/campaign-01/execute", json={"limit": 3}).status_code == 409

    preflight = client.post("/api/campaigns/campaign-01/preflight", json={})
    assert preflight.status_code == 200
    assert len(preflight.json()["completed"]) == 1
    assert preflight.json()["status"]["completed_runs"] == 1
    assert preflight.json()["status"]["remaining_runs"] == 86

    replay = client.post("/api/campaigns/campaign-01/preflight", json={})
    assert replay.status_code == 200
    assert replay.json()["completed"][0]["run_id"] != preflight.json()["completed"][0]["run_id"]
    assert replay.json()["status"]["completed_runs"] == 2

    locked = client.post("/api/campaigns/campaign-01/lock", json={})
    assert locked.status_code == 200
    assert locked.json()["preregistration"]["status"] == "locked"
    assert locked.json()["signature"] == "NicoMrx"

    batch = client.post("/api/campaigns/campaign-01/execute", json={"limit": 3, "pace_seconds": 0})
    assert batch.status_code == 200
    assert len(batch.json()["completed"]) == 3
    assert batch.json()["status"]["completed_runs"] == 5
    assert batch.json()["status"]["remaining_runs"] == 82

    # Re-saving an identical locked source is idempotent and cannot unlock it.
    resaved = client.post("/api/campaigns/legacy/save", json=payload)
    assert resaved.status_code == 200
    assert resaved.json()["preregistration"]["status"] == "locked"
    assert resaved.json()["completed_runs"] == 5
