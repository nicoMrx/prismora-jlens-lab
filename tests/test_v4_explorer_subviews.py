from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
PKG = ROOT / "prismora_lab" / "assets" / "web"
ASSETS = (
    "v4-explorer-subviews.js",
    "v4-explorer-subviews.css",
    "v4-token-tooltip.js",
)


def test_v4_explorer_subviews_use_real_artifacts_and_verified_comparison():
    script = (WEB / "v4-explorer-subviews.js").read_text(encoding="utf-8")

    assert "prismora.v4.exploreView" in script
    assert "sessionStorage.getItem(SESSION_KEY)" in script
    assert "normalizeNative" in script
    assert "layers_by_type" in script
    assert "original_filename" in script
    assert "coverage" in script

    assert "request.intervention" in script
    assert "steerLayers" in script
    assert "steerTokens" in script
    assert "steerAblate" in script
    assert "preuve causale" in script

    assert "/api/demo/build-week/understand/compare" in script
    assert "demo-pair-a-control" in script
    assert "demo-pair-a-shift" in script
    assert "probability_abs_tolerance" in script
    assert "rule_id" in script
    assert "template_id" in script

    assert "DONNEES" not in script
    assert "https://" not in script


def test_v4_explorer_cards_become_keyboard_accessible_real_subviews():
    script = (WEB / "v4-explorer-subviews.js").read_text(encoding="utf-8")
    css = (WEB / "v4-explorer-subviews.css").read_text(encoding="utf-8")

    for view in ("understand", "compare", "baselines", "interventions"):
        assert view in script
    assert "data-explorer-view" in script
    assert "role', 'button'" in script
    assert "['Enter', ' ']" in script
    assert "explorer-subview[hidden]" in css
    assert "explorer-fact-grid" in css
    assert "explorer-causal-guard" in css


def test_v4_explorer_module_has_static_loading_and_dynamic_fallback():
    html = (WEB / "v4.html").read_text(encoding="utf-8")
    packaged_html = (PKG / "v4.html").read_text(encoding="utf-8")
    loader = (WEB / "v4-token-tooltip.js").read_text(encoding="utf-8")

    assert 'href="/v4-explorer-subviews.css?v=1"' in html
    assert 'src="/v4-explorer-subviews.js?v=1"' in html
    assert 'data-prismora-explorer-subviews="1"' in html
    assert html.index('/v4-explorer-subviews.js?v=1') < html.index('/v4-token-tooltip.js?v=1')
    assert html == packaged_html

    assert "/v4-explorer-subviews.css?v=1" in loader
    assert "/v4-explorer-subviews.js?v=1" in loader
    assert "v4-explorer-router.js" not in loader
    assert "v4-explorer-reference.js" not in loader


def test_v4_explorer_assets_are_identical_between_source_and_package():
    for name in ASSETS:
        assert (WEB / name).read_text(encoding="utf-8") == (PKG / name).read_text(encoding="utf-8")
