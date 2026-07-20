from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
PKG = ROOT / "prismora_lab" / "assets" / "web"


def test_v4_demo_library_loads_verified_real_pairs_campaign_and_final_channel():
    script = (WEB / "v4-demo-library.js").read_text(encoding="utf-8")
    restore = (WEB / "v4-demo-restore.js").read_text(encoding="utf-8")
    css = (WEB / "v4-demo-library.css").read_text(encoding="utf-8")
    loader = (WEB / "v4-token-tooltip.js").read_text(encoding="utf-8")
    html = (WEB / "v4.html").read_text(encoding="utf-8")

    assert "/api/demo/showcase" in script
    assert "prismora.v4.comparisonB" in script
    assert "prismora.v4.loadCampaignDemo" in script
    assert "DataTransfer" in script
    assert "default_channel" not in script  # channel choice belongs to the verified artifact
    assert "final normalisé" in script
    assert "un candidat décodable ne prouve ni conscience" in script
    assert "NicoMrx" in script
    assert "openCampaign" in script
    assert "restoreComparisonB" in script

    assert "restoreCampaignDemo" in restore
    assert "enforceCampaignGuards" in restore
    assert "campaign-demo" in restore
    assert "remaining" in restore

    assert ".demo-library-dialog" in css
    assert ".demo-card.real" in css
    assert ".demo-card.campaign" in css

    positions = [loader.index(path) for path in (
        "/v4-campaign-center.js?v=1",
        "/v4-demo-library.js?v=1",
        "/v4-demo-restore.js?v=1",
    )]
    assert positions == sorted(positions)
    assert "/v4-demo-library.css?v=1" in loader
    assert "demos.async = false" in loader
    assert "restore.async = false" in loader

    # Critical showcase assets are also loaded directly, with a bumped cache key.
    assert '<link rel="stylesheet" href="/v4-demo-library.css?v=2"' in html
    assert '<script src="/v4-demo-library.js?v=2"' in html
    assert '<script src="/v4-demo-restore.js?v=2"' in html
    assert '<script src="/v4-token-tooltip.js?v=2"' in html


def test_v4_demo_library_assets_are_identical_between_source_and_package():
    for name in (
        "v4-demo-library.js",
        "v4-demo-library.css",
        "v4-demo-restore.js",
        "v4-token-tooltip.js",
        "v4.html",
    ):
        assert (WEB / name).read_text(encoding="utf-8") == (PKG / name).read_text(encoding="utf-8")


def test_demo_library_ui_contains_no_secret_or_remote_raw_url():
    combined = "\n".join((WEB / name).read_text(encoding="utf-8") for name in (
        "v4-demo-library.js", "v4-demo-restore.js", "v4-campaign-center.js"
    ))
    for forbidden in ("NEURONPEDIA_API_KEY", "BEGIN PRIVATE KEY", "Julie", "raw.githubusercontent.com", "https://"):
        assert forbidden not in combined
