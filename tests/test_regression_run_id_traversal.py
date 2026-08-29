"""
Test de régression — défaut (a) de l'audit croisé Opus/Pepper du 12/08 et du rapport Cowork 08 (27/08).

POST /api/import/neuronpedia accepte un run_id fourni par l'appelant et store.run_dir() le concatène
sans confinement. Un run_id de la forme ../../../../x écrit raw.json et artifact.json HORS du data_dir.

Ce test doit ÉCHOUER sur un checkout non corrigé (53e5946 remote, 21/07) et PASSER après B3
(pattern sur run_id dans run-artifact-v2 + confinement dans store.run_dir + validation à l'entrée).

Déposer dans tests/ sous le nom test_regression_run_id_traversal.py.
"""
import asyncio
import json
from pathlib import Path

from fastapi.testclient import TestClient

from prismora_lab.api.app import create_app
from prismora_lab.backends.mock import MockBackend
from prismora_lab.config import Settings

ROOT = Path(__file__).resolve().parents[1]


def _client(data_dir: Path) -> TestClient:
    return TestClient(create_app(Settings(data_dir=data_dir, neuronpedia_api_key=None, worker_url=None, max_runs_per_request=8)))


def _mock_raw(text: str) -> dict:
    request = {
        "backend": "mock",
        "model": {"alias": "M", "model_id": "qwen3.6-27b"},
        "prompt_id": "source",
        "chat": [{"role": "user", "content": text}],
        "factors": {},
        "repeat": 1,
        "generation": {"temperature": 0, "max_new_tokens": 12, "prepend_bos": True, "enable_thinking": False},
        "readout": {"types": ["LOGIT_LENS", "JACOBIAN_LENS"], "top_k": 8, "filter_nonword_tokens": True},
        "intervention": None,
    }
    return request, asyncio.run(MockBackend().run(request)).value


def test_import_run_id_cannot_escape_data_dir(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    outside = tmp_path / "outside"  # cible hors data_dir
    client = _client(data_dir)

    spec = json.loads((ROOT / "examples" / "strategy_quadratic_mock.json").read_text())
    assert client.post("/api/experiments", json=spec).status_code == 200

    request, raw = _mock_raw("traversal probe")
    evil_run_id = "../../../../outside/escape-run"  # <data_dir>/experiments/<id>/runs/ + 4 niveaux = tmp_path
    response = client.post(
        "/api/import/neuronpedia",
        json={"experiment_id": spec["experiment_id"], "request": request, "raw": raw, "run_id": evil_run_id},
    )

    escaped = sorted(str(p.relative_to(tmp_path)) for p in outside.rglob("*") if p.is_file()) if outside.exists() else []
    runs_dir = data_dir / "experiments" / spec["experiment_id"] / "runs"
    stray = sorted(str(p.relative_to(data_dir)) for p in data_dir.rglob("*.json")
                   if p.is_file() and p.name in ("raw.json", "artifact.json") and runs_dir not in p.parents)

    # Contrat attendu après correctif : refus (4xx) ET aucun fichier hors data_dir.
    assert response.status_code >= 400, f"run_id traversant accepté (HTTP {response.status_code}) ; fichiers hors data_dir : {escaped}"
    assert escaped == [], f"fichiers écrits hors data_dir : {escaped}"
    assert stray == [], f"artefacts écrits hors experiments/<id>/runs : {stray}"
