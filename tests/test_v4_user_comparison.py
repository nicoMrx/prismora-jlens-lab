from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
PKG = ROOT / "prismora_lab" / "assets" / "web"


def test_user_selected_comparison_is_local_deterministic_and_guarded():
    script = (WEB / "v4-user-comparison.js").read_text(encoding="utf-8")
    css = (WEB / "v4-user-comparison.css").read_text(encoding="utf-8")

    assert "compareArtifacts" in script
    assert "promptPairs" in script
    assert "generatedPairs" in script
    assert "commonLayers" in script
    assert "probability" in script
    assert "strictCellChanged" in script
    assert "sameArray(left.top_tokens, right.top_tokens)" in script
    assert "sameNumericArrayWithinTolerance(left.top_probs, right.top_probs, tolerance)" in script
    assert "interventionLayers" in script
    assert "preuve causale" in script
    assert "Aucun export n’est archivé automatiquement" in script
    assert "type=\"file\"" in script
    assert "sessionStorage.getItem(SESSION_KEY)" in script
    assert "fetch(" not in script
    assert "https://" not in script

    # The DOM observer must only reattach the workbench when the parent view removed it.
    assert "if (panel && !$('.user-comparison-workbench', panel)) schedule();" in script
    assert "new MutationObserver(schedule)" not in script

    assert ".user-comparison-workbench" in css
    assert ".user-comparison-artifacts" in css
    assert ".user-comparison-controls" in css


def test_user_comparison_assets_are_loaded_after_explorer_and_packaged():
    loader = (WEB / "v4-token-tooltip.js").read_text(encoding="utf-8")
    assert "/v4-user-comparison.css?v=1" in loader
    assert "/v4-user-comparison.js?v=1" in loader
    assert loader.index("/v4-explorer-subviews.js?v=1") < loader.index("/v4-user-comparison.js?v=1")
    assert "userComparison.async = false" in loader

    for name in ("v4-user-comparison.js", "v4-user-comparison.css", "v4-token-tooltip.js"):
        assert (WEB / name).read_text(encoding="utf-8") == (PKG / name).read_text(encoding="utf-8")


def test_frontend_dynamic_html_is_escaped_or_built_with_text_content():
    legacy = (WEB / "app.js").read_text(encoding="utf-8")
    showcase = (WEB / "v4-showcase-insights.js").read_text(encoding="utf-8")
    assert "replace(/[&<>\"']/g" in legacy
    coverage = legacy.split("function renderUnderstand()", 1)[1].split("function clearUnderstandError", 1)[0]
    for value in (
        "statusLabel(status)", "c.source_tokens_total", "c.transmitted_tokens",
        "c.instrumented_tokens", "c.instrumented_generated_tokens",
    ):
        assert f"escapeText({value}" in coverage
    assert "escapeText((c.captured_layers" in coverage
    assert "control.innerHTML" not in showcase
    assert "label.textContent = t('control')" in showcase
    assert "detail.textContent = t('controlText')" in showcase
