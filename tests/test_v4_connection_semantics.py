from pathlib import Path

from fastapi.testclient import TestClient

from prismora_lab.api.app import create_app
from prismora_lab.config import Settings
from prismora_lab.store import LabStore


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
PKG = ROOT / "prismora_lab" / "assets" / "web"


def test_connection_semantics_ui_distinguishes_saved_tested_and_rejected():
    source = (WEB / "v4-connection-semantics.js").read_text(encoding="utf-8")
    packaged = (PKG / "v4-connection-semantics.js").read_text(encoding="utf-8")
    assert source == packaged
    assert "Clé Neuronpedia enregistrée · test requis" in source
    assert "Clé Neuronpedia refusée" in source
    assert "Neuronpedia connecté" in source
    assert "neuronpedia_key_configured" in source
    assert "neuronpedia_connected" in source
    assert "/api/session/settings" in source
    assert "Enregistrer et tester" in source
    assert "effacée à chaque redémarrage de Prismora" in source
    assert "État de la session" in source
    assert "connection-session-state" in source
    assert "NEURONPEDIA_API_KEY" not in source


def test_v4_route_injects_connection_semantics_before_campaign_modules(tmp_path):
    client = TestClient(
        create_app(
            Settings(data_dir=tmp_path, neuronpedia_api_key=None, worker_url=None),
            store=LabStore(tmp_path),
        )
    )
    response = client.get("/v4.html?v=connection-test")
    assert response.status_code == 200
    html = response.text
    connection = '/v4-connection-semantics.js?v=1'
    campaign = '/v4-campaign-center.js?v=2'
    assert connection in html
    assert campaign in html
    assert html.index(connection) < html.index(campaign)
