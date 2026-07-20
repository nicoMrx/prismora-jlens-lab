from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
PKG = ROOT / "prismora_lab" / "assets" / "web"


def test_v4_explorer_has_two_lens_tables_and_one_overlay():
    for root in (WEB, PKG):
        script = (root / "v4-lens-comparison.js").read_text(encoding="utf-8")
        css = (root / "v4-lens-comparison.css").read_text(encoding="utf-8")
        tooltip = (root / "v4-token-tooltip.js").read_text(encoding="utf-8")
        assert "Tableau Jacobian Lens" in script
        assert "Tableau Logit Lens" in script
        assert "Superposition des trajectoires top-1" in script
        assert "JACOBIAN_LENS" in script
        assert "LOGIT_LENS" in script
        assert "agreementCount" in script
        assert "firstDifferenceIndex" in script
        assert "does not claim that Jacobian and Logit represent the same internal mechanism" in script
        assert "/v4-lens-comparison.js" in tooltip
        assert "/v4-lens-comparison.css" in tooltip
        assert ".overlay-line.jacobian" in css
        assert ".overlay-line.logit" in css
        assert "var(--violet)" in css
        assert "var(--teal)" in css
        assert "fetch(" not in script
        assert "/api/" not in script


def test_v4_lens_comparison_assets_are_identical_between_source_and_package():
    for name in ("v4-lens-comparison.js", "v4-lens-comparison.css"):
        assert (WEB / name).read_text(encoding="utf-8") == (PKG / name).read_text(encoding="utf-8")
