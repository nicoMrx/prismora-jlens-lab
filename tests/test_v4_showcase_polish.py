from pathlib import Path

from fastapi.testclient import TestClient

from prismora_lab.api.app import create_app
from prismora_lab.config import Settings
from prismora_lab.store import LabStore


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
PKG = ROOT / "prismora_lab" / "assets" / "web"


def test_campaign_polish_is_idempotent_focused_and_packaged():
    script = (WEB / "v4-campaign-polish.js").read_text(encoding="utf-8")
    css = (WEB / "v4-campaign-polish.css").read_text(encoding="utf-8")

    assert "ensureCampaignNav" in script
    assert "if (button.textContent !== label)" in script
    assert "campaign-focus" in script
    assert "requestAnimationFrame" in script
    assert ".campaign-focus" in css
    assert "#campaign-center-panel" in css

    for name in ("v4-campaign-polish.js", "v4-campaign-polish.css"):
        assert (WEB / name).read_text(encoding="utf-8") == (PKG / name).read_text(encoding="utf-8")


def test_showcase_insights_surface_real_metrics_controls_and_limits_without_render_loop():
    script = (WEB / "v4-showcase-insights.js").read_text(encoding="utf-8")
    css = (WEB / "v4-showcase-insights.css").read_text(encoding="utf-8")

    assert "Meta Capture — lecture instrumentale" in script
    assert "Cellules top-8" in script
    assert "Cellules top-1" in script
    assert "Probabilité max." in script
    assert "Lexicalisé dans le final" in script
    assert "Contrôles branche A" in script
    assert "final normalisé" in script
    assert "ne prouve ni conscience" in script
    assert "dataset.renderKey" in script
    assert "existing?.dataset.renderKey === key" in script
    assert "document.readyState === 'loading'" in script
    assert ".showcase-insights" in css
    assert ".showcase-model-grid" in css
    assert ".showcase-pair-active" in css

    for name in ("v4-showcase-insights.js", "v4-showcase-insights.css"):
        assert (WEB / name).read_text(encoding="utf-8") == (PKG / name).read_text(encoding="utf-8")


def test_guarded_v4_route_injects_polish_before_campaign_modules(tmp_path):
    client = TestClient(
        create_app(
            Settings(data_dir=tmp_path, neuronpedia_api_key=None, worker_url=None),
            store=LabStore(tmp_path),
        )
    )
    response = client.get("/v4.html?v=showcase-polish")
    assert response.status_code == 200
    html = response.text

    guard = '/v4-sidebar-observer-guard.js?v=1'
    campaign_polish = '/v4-campaign-polish.js?v=1'
    showcase = '/v4-showcase-insights.js?v=1'
    campaign = '/v4-campaign-center.js?v=2'

    for asset in (
        '/v4-campaign-polish.css?v=1',
        '/v4-showcase-insights.css?v=1',
        guard,
        campaign_polish,
        showcase,
    ):
        assert asset in html

    assert html.index(guard) < html.index(campaign_polish) < html.index(showcase) < html.index(campaign)
    assert "no-store" in response.headers.get("cache-control", "")


def test_demo_restore_loads_polish_assets_as_fallback():
    source = (WEB / "v4-demo-restore.js").read_text(encoding="utf-8")
    packaged = (PKG / "v4-demo-restore.js").read_text(encoding="utf-8")
    assert source == packaged
    assert "/v4-campaign-polish.css?v=1" in source
    assert "/v4-showcase-insights.css?v=1" in source
    assert "/v4-campaign-polish.js?v=1" in source
    assert "/v4-showcase-insights.js?v=1" in source
    assert "script.async = false" in source
