from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
PKG = ROOT / "prismora_lab" / "assets" / "web"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_source_and_packaged_web_are_synchronized():
    for name in ("index.html", "app.js", "styles.css"):
        assert read(WEB / name) == read(PKG / name)


def test_progressive_interface_has_no_required_cdn_dependency():
    combined = "\n".join(read(WEB / name) for name in ("index.html", "styles.css", "app.js"))
    forbidden = ("fonts.googleapis.com", "fonts.gstatic.com", "cdn.jsdelivr.net", "unpkg.com")
    assert not any(item in combined for item in forbidden)


def test_persisted_theme_and_level_keys_exist():
    app = read(WEB / "app.js")
    assert "prismora.theme" in app
    assert "prismora.level" in app
    assert "prismora.locale" in app


def test_old_visualizer_hash_compatibility_and_state_preservation_hooks():
    app = read(WEB / "app.js")
    assert "targetPanel === 'visualizer'" in app
    assert "state.readerSelectedToken" in app
    assert "state.readerSelectedLayer" in app
    assert "renderReader()" in app


def test_reader_loads_verified_demo_and_keeps_real_output_visible():
    app = read(WEB / "app.js")
    html = read(WEB / "index.html")
    assert "/api/demo/build-week" in app
    assert "readerOutput" in html
    assert "generated_text" in app or "completion" in app


def test_captured_layers_only_and_no_interpolation_language():
    app = read(WEB / "app.js")
    assert "captured_layers" in app
    assert "unmeasured" in app
    assert "interpol" not in app.lower()


def test_actual_top8_extraction_and_no_production_donnees_dataset():
    app = read(WEB / "app.js")
    assert ".slice(0, 8)" in app
    combined = read(WEB / "index.html") + read(WEB / "app.js")
    assert "DONNEES" not in combined


def test_gemma_disabled_or_coming_soon_registry_copy():
    app = read(WEB / "app.js")
    assert "gemma" in app.lower()
    assert "coming soon" in app.lower() and "disabled" in app.lower()
    assert "à venir" in app.lower() and "désactivé" in app.lower()


def test_dynamic_content_is_not_destructively_replaced_by_static_i18n():
    app = read(WEB / "app.js")
    assert "document.querySelectorAll('[data-i18n]')" in app
    assert "if (!state.visualComparison)" in app
    assert "readerOutput" not in app.split("function applyI18n()", 1)[1].split("async function api", 1)[0]


def _demo_artifact():
    import json
    return json.loads((ROOT / "demo" / "build_week_2026" / "demo-pair-a-control.json").read_text())


def _generated_tokens(artifact):
    return [tok for tok in artifact["result"]["tokens"] if tok.get("is_generated") or tok.get("generated") or tok.get("role") == "generated"]


def _demo_top_candidates(artifact, token, layer):
    layers = artifact["result"]["meta"]["layers_by_type"]["JACOBIAN_LENS"]
    index = layers.index(layer)
    result = token["results"][0]
    return list(zip(result["top_tokens"][index], result["top_probs"][index]))[:8]


def test_verified_demo_reader_has_real_candidates_and_trajectory_values():
    artifact = _demo_artifact()
    token = _generated_tokens(artifact)[0]
    layers = artifact["result"]["meta"]["layers_by_type"]["JACOBIAN_LENS"]
    valid = [layer for layer in layers if _demo_top_candidates(artifact, token, layer)]
    assert valid
    selected_layer = valid[-1]
    top = _demo_top_candidates(artifact, token, selected_layer)
    assert top and top[0][0]
    candidate = top[0][0]
    trajectory = [prob for layer in layers for tok, prob in _demo_top_candidates(artifact, token, layer) if tok == candidate]
    assert trajectory and all(isinstance(prob, float) for prob in trajectory)


def test_level_buttons_navigate_to_level_defaults():
    app = read(WEB / "app.js")
    assert "defaultPanelForLevel(level)" in app
    assert "'explore' ? 'visualizer'" in app
    assert "'control' ? 'dashboard'" in app
    assert "navigate(defaultPanelForLevel(state.level))" in app


def test_french_reader_visualizer_catalogue_uses_token_not_jeton():
    app = read(WEB / "app.js")
    french_catalogue = app.split("fr: {", 1)[1].split("}\n  };", 1)[0]
    assert "'nav.reader': 'Lire'" in french_catalogue
    assert "'reader.understand': 'Comprendre'" in french_catalogue
    assert "jeton" not in french_catalogue.lower()


def test_light_theme_neutralizes_legacy_reader_backgrounds():
    styles = read(WEB / "styles.css")
    assert ':root[data-theme="light"]' in styles
    assert ".reader-conversation,.reader-jlens-card,.reader-understand" in styles
    assert "background:var(--panel)" in styles
    assert "input,select,textarea" in styles and "color:var(--text)" in styles
