from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
PKG = ROOT / "prismora_lab" / "assets" / "web"


def test_v4_comparison_classifies_strict_partial_and_cross_model_pairs_locally():
    script = (WEB / "v4-explorer-polish.js").read_text(encoding="utf-8")
    css = (WEB / "v4-user-comparison.css").read_text(encoding="utf-8")

    assert "Paire A/B stricte" in script
    assert "Comparaison exploratoire inter-modèles" in script
    assert "Compatibilité partielle" in script
    assert "promptTokenIds" in script
    assert "sameArray" in script
    assert "comparabilityConfiguration" in script
    assert "sameConfiguration" in script
    for field in (
        "revision", "tokenizer_revision", "lens_revision", "precision", "quantization",
        "generation", "readout", "transmitted_tokens", "instrumented_tokens", "captured_layers",
    ):
        assert field in script
    assert "Compatibilité partielle · configuration différente" in script
    assert "modelId" in script
    assert "user-comparison-compatibility" in script
    assert ".user-comparison-compatibility" in css
    assert ".user-comparison-compatibility.strict" in css
    assert ".user-comparison-compatibility.exploratory" in css
    assert "fetch(" not in script
    assert "https://" not in script


def test_v4_comparison_compatibility_assets_are_packaged_identically():
    for name in ("v4-explorer-polish.js", "v4-user-comparison.css"):
        assert (WEB / name).read_text(encoding="utf-8") == (PKG / name).read_text(encoding="utf-8")


def test_local_runtime_artifacts_are_ignored_by_git():
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for pattern in ("__pycache__/", "*.py[cod]", ".pytest_cache/", ".prismora-data/", ".env"):
        assert pattern in gitignore
