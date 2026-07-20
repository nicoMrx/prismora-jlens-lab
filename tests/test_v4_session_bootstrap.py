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


def test_v4_source_and_packaged_shell_are_identical():
    for name in ("v4.html", "v4-session-bootstrap.js"):
        assert (WEB / name).read_text(encoding="utf-8") == (PKG / name).read_text(encoding="utf-8")
