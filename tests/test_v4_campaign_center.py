from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
PKG = ROOT / "prismora_lab" / "assets" / "web"


def test_v4_campaign_center_is_progressive_resumable_and_signed():
    script = (WEB / "v4-campaign-center.js").read_text(encoding="utf-8")
    css = (WEB / "v4-campaign-center.css").read_text(encoding="utf-8")
    loader = (WEB / "v4-token-tooltip.js").read_text(encoding="utf-8")
    html = (WEB / "v4.html").read_text(encoding="utf-8")

    assert "Centre de campagnes" in script
    assert "NicoMrx" in script
    assert "/api/demo/campaign-01" in script
    assert "/api/campaigns/legacy/preview" in script
    assert "/api/campaigns/legacy/save" in script
    assert "/preflight" in script
    assert "/execute" in script
    assert "pace_seconds" in script
    assert "filter_nonword_tokens" in script
    assert "condition_count" in script and "run_count" in script
    assert "type=\"file\"" in script
    assert ".campaign-progress" in css
    assert ".campaign-conditions" in css
    assert "/v4-campaign-center.css?v=1" in loader
    assert "/v4-campaign-center.js?v=1" in loader
    assert "campaign.async = false" in loader
    assert "NEURONPEDIA_API_KEY" not in script

    assert '<link rel="stylesheet" href="/v4-campaign-center.css?v=2"' in html
    assert '<script src="/v4-campaign-center.js?v=2"' in html


def test_v4_campaign_center_assets_are_identical_between_source_and_package():
    for name in ("v4-campaign-center.js", "v4-campaign-center.css", "v4-token-tooltip.js", "v4.html"):
        assert (WEB / name).read_text(encoding="utf-8") == (PKG / name).read_text(encoding="utf-8")
