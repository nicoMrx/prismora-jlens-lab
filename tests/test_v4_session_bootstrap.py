from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
PKG = ROOT / "prismora_lab" / "assets" / "web"


def test_v4_session_bootstrap_runs_before_main_app_and_is_packaged():
    for root in (WEB, PKG):
        html = (root / "v4.html").read_text(encoding="utf-8")
        bootstrap = (root / "v4-session-bootstrap.js").read_text(encoding="utf-8")
        assert html.index("/v4-session-bootstrap.js") < html.index("/v4-app.js")
        assert "prismora.v4.session" in bootstrap
        assert "protectFirstStartupRemoval" in bootstrap
        assert "Storage.prototype.removeItem" in bootstrap


def test_v4_native_neuronpedia_import_normalizes_without_network_or_api_key():
    bootstrap = (WEB / "v4-session-bootstrap.js").read_text(encoding="utf-8")
    assert "isNeuronpediaExport" in bootstrap
    assert "normalizeNeuronpediaExport" in bootstrap
    assert "value?.version === 1" in bootstrap
    assert "['chat', 'completion']" in bootstrap
    assert "layers_by_type" in bootstrap
    assert "neuronpedia_export" in bootstrap
    assert "new DataTransfer()" in bootstrap
    assert "new File([JSON.stringify(source)]" in bootstrap
    assert "fetch(" not in bootstrap
    assert "neuronpedia_api_key" not in bootstrap


def test_v4_dense_layer_layout_stays_inside_the_measurement_card():
    bootstrap = (WEB / "v4-session-bootstrap.js").read_text(encoding="utf-8")
    assert "count > 24" in bootstrap
    assert "positionForIndex" in bootstrap
    assert "layer % 8 === 0" in bootstrap
    assert "normalizeDenseMeasurements" in bootstrap
    assert "MutationObserver" in bootstrap
    assert "point.style.left" in bootstrap


def test_v4_source_and_packaged_shell_are_identical():
    for name in ("v4.html", "v4-session-bootstrap.js"):
        assert (WEB / name).read_text(encoding="utf-8") == (PKG / name).read_text(encoding="utf-8")
