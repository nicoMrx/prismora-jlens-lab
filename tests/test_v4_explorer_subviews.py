from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
PKG = ROOT / "prismora_lab" / "assets" / "web"
ASSETS = (
    "v4-explorer-router.js",
    "v4-explorer-reference.js",
    "v4-explorer-interventions.js",
    "v4-explorer-compare.js",
    "v4-explorer-subviews.css",
)


def test_v4_explorer_subviews_use_real_artifacts_and_verified_comparison():
    router = (WEB / "v4-explorer-router.js").read_text(encoding="utf-8")
    reference = (WEB / "v4-explorer-reference.js").read_text(encoding="utf-8")
    interventions = (WEB / "v4-explorer-interventions.js").read_text(encoding="utf-8")
    comparison = (WEB / "v4-explorer-compare.js").read_text(encoding="utf-8")

    assert "prismora.v4.exploreView" in router
    assert "prismora:explorer-view" in router
    assert "normalizeNative" in router
    assert "runtimeArtifact" in router
    assert "data-explorer-panel" in router

    assert "layers_by_type" in reference
    assert "original_filename" in reference
    assert "coverage" in reference

    assert "request.intervention" in interventions
    assert "steerLayers" in interventions
    assert "steerTokens" in interventions
    assert "steerAblate" in interventions
    assert "preuve causale" in interventions

    assert "/api/demo/build-week/understand/compare" in comparison
    assert "demo-pair-a-control" in comparison
    assert "demo-pair-a-shift" in comparison
    assert "probability_abs_tolerance" in comparison
    assert "rule_id" in comparison
    assert "template_id" in comparison

    combined = router + reference + interventions + comparison
    assert "DONNEES" not in combined
    assert "https://" not in combined


def test_v4_explorer_modules_are_loaded_in_order_by_the_existing_enhancement_loader():
    loader = (WEB / "v4-token-tooltip.js").read_text(encoding="utf-8")
    assert "/v4-explorer-subviews.css?v=1" in loader
    positions = [loader.index(f"/v4-explorer-{name}.js?v=1") for name in ("router", "reference", "interventions", "compare")]
    assert positions == sorted(positions)
    assert "script.async = false" in loader


def test_v4_explorer_assets_are_identical_between_source_and_package():
    for name in (*ASSETS, "v4-token-tooltip.js"):
        assert (WEB / name).read_text(encoding="utf-8") == (PKG / name).read_text(encoding="utf-8")
