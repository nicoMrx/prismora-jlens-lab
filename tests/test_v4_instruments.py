from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
PKG = ROOT / "prismora_lab" / "assets" / "web"


def test_v4_lens_selector_uses_existing_artifact_without_network():
    for root in (WEB, PKG):
        html = (root / "v4.html").read_text(encoding="utf-8")
        script = (root / "v4-instruments.js").read_text(encoding="utf-8")
        assert "/v4-instruments.js" in html
        assert html.index("/v4-app.js") < html.index("/v4-instruments.js")
        assert "JACOBIAN_LENS" in script
        assert "LOGIT_LENS" in script
        assert "lens-select" in script
        assert "layers_by_type" in script
        assert "top_tokens" in script
        assert "top_probs" in script
        assert "fetch(" not in script
        assert "/api/" not in script


def test_v4_understand_is_deterministic_and_has_no_overinterpretation_guard():
    script = (WEB / "v4-instruments.js").read_text(encoding="utf-8")
    css = (WEB / "v4-refinements.css").read_text(encoding="utf-8")
    assert "Understand — factual reading" in script
    assert "Comprendre — lecture factuelle" in script
    assert "does not infer intent, bias, censorship" in script
    assert "n’infère ni intention, ni biais, ni censure" in script
    assert "firstTopOneChange" in script
    assert "unmeasuredRanges" in script
    assert "understand-panel" in script
    assert ".understand-panel" in css
    assert ".understand-grid" in css


def test_v4_instrument_assets_are_identical_between_source_and_package():
    for name in ("v4.html", "v4-instruments.js", "v4-refinements.css"):
        assert (WEB / name).read_text(encoding="utf-8") == (PKG / name).read_text(encoding="utf-8")
