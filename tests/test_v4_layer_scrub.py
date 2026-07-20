from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
PKG = ROOT / "prismora_lab" / "assets" / "web"


def test_v4_layer_scrub_updates_reader_and_overlay_without_network():
    for root in (WEB, PKG):
        script = (root / "v4-layer-scrub.js").read_text(encoding="utf-8")
        tooltip = (root / "v4-token-tooltip.js").read_text(encoding="utf-8")
        css = (root / "v4-lens-comparison.css").read_text(encoding="utf-8")
        assert "nearestLayerFromRail" in script
        assert "nearestLayerFromOverlay" in script
        assert "entry.button.click()" in script
        assert "pointermove" in script
        assert "layer-hover-badge" in script
        assert "suppressNativeOverlayTooltips" in script
        assert "querySelectorAll('title')" in script
        assert "/v4-layer-scrub.js" in tooltip
        assert ".layer-hover-badge" in css
        assert "cursor:crosshair" in css
        assert ".lens-overlay-chart .overlay-point{pointer-events:none}" in css
        assert "fetch(" not in script
        assert "/api/" not in script


def test_v4_layer_scrub_assets_are_identical_between_source_and_package():
    for name in ("v4-layer-scrub.js", "v4-token-tooltip.js", "v4-lens-comparison.css"):
        assert (WEB / name).read_text(encoding="utf-8") == (PKG / name).read_text(encoding="utf-8")
