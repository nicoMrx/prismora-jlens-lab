from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
PKG = ROOT / "prismora_lab" / "assets" / "web"


def test_v4_token_tooltip_is_local_bilingual_and_packaged():
    for root in (WEB, PKG):
        html = (root / "v4.html").read_text(encoding="utf-8")
        script = (root / "v4-token-tooltip.js").read_text(encoding="utf-8")
        css = (root / "v4-refinements.css").read_text(encoding="utf-8")
        assert "/v4-token-tooltip.js" in html
        assert "/v4-refinements.css" in html
        assert "中国" in script
        assert "Chine" in script
        assert "China" in script
        assert "glavni grad" in script
        assert "fetch(" not in script
        assert ".token-tooltip" in css
        assert "max-width:1600px" in css


def test_v4_selected_token_in_jlens_title_uses_the_same_tooltip():
    script = (WEB / "v4-token-tooltip.js").read_text(encoding="utf-8")
    css = (WEB / "v4-refinements.css").read_text(encoding="utf-8")
    assert "enhanceJlensTitle" in script
    assert ".jlens-title-token" in script
    assert ".candidate strong, .jlens-title-token" in script
    assert "MutationObserver(enhanceJlensTitle)" in script
    assert ".jlens-title-token" in css


def test_v4_tooltip_assets_are_identical_between_source_and_package():
    for name in ("v4-token-tooltip.js", "v4-refinements.css"):
        assert (WEB / name).read_text(encoding="utf-8") == (PKG / name).read_text(encoding="utf-8")
