from pathlib import Path

from fastapi.testclient import TestClient

from prismora_lab.api.app import create_app
from prismora_lab.config import Settings
from prismora_lab.store import LabStore


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
PKG = ROOT / "prismora_lab" / "assets" / "web"


def test_sidebar_guard_is_targeted_and_packaged():
    source = (WEB / "v4-sidebar-observer-guard.js").read_text(encoding="utf-8")
    packaged = (PKG / "v4-sidebar-observer-guard.js").read_text(encoding="utf-8")
    assert source == packaged
    assert "target?.id === 'sidebar-nav'" in source
    assert "suppressUntilNextFrame" in source
    assert "requestAnimationFrame" in source
    assert "window.MutationObserver = PrismoraMutationObserver" in source


def test_v4_route_injects_guard_before_campaign_and_demo_modules(tmp_path):
    client = TestClient(
        create_app(
            Settings(data_dir=tmp_path, neuronpedia_api_key=None, worker_url=None),
            store=LabStore(tmp_path),
        )
    )
    response = client.get("/v4.html?v=test")
    assert response.status_code == 200
    html = response.text
    guard = '/v4-sidebar-observer-guard.js?v=1'
    assert guard in html
    assert html.index(guard) < html.index('/v4-campaign-center.js?v=2')
    assert html.index(guard) < html.index('/v4-demo-library.js?v=2')
    assert "no-store" in response.headers.get("cache-control", "")
