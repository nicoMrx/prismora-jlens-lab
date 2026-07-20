from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
PACKAGED = ROOT / "prismora_lab" / "assets" / "web"


def test_v4_uses_internal_levels_and_exact_mark() -> None:
    html = (WEB / "v4.html").read_text(encoding="utf-8")
    js = (WEB / "v4-app.js").read_text(encoding="utf-8")

    assert '/assets/prismora-mark.svg' in html
    assert 'data-screen="read"' in html
    assert 'data-screen="explore"' in html
    assert 'data-screen="control"' in html
    assert 'location.href' not in js
    assert "screen(level.dataset.level)" in js


def test_v4_restores_small_artifact_in_session_only() -> None:
    js = (WEB / "v4-app.js").read_text(encoding="utf-8")

    assert "const SESSION_KEY = 'prismora.v4.session'" in js
    assert 'sessionStorage.setItem(SESSION_KEY' in js
    assert 'sessionStorage.getItem(SESSION_KEY)' in js
    assert 'sessionStorage.removeItem(SESSION_KEY)' in js
    assert 'localStorage.setItem(SESSION_KEY' not in js
    assert 'MAX_SESSION_BYTES = 2_000_000' in js


def test_v4_cache_bust_and_packaged_assets_exist() -> None:
    html = (WEB / "v4.html").read_text(encoding="utf-8")

    assert '/v4-app.css?v=2' in html
    assert '/v4-app.js?v=2' in html
    for relative in ("v4.html", "v4-app.css", "v4-app.js", "assets/prismora-mark.svg"):
        assert (WEB / relative).exists()
        assert (PACKAGED / relative).exists()
