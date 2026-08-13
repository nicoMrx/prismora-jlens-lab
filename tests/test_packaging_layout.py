from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_installable_asset_tree_contains_frontend_fonts_and_demos():
    packaged = ROOT / "prismora_lab" / "assets"
    for relative in (
        "web/index.html",
        "web/v4.html",
        "web/app.js",
        "web/v4-app.js",
        "web/assets/prismora-mark.svg",
        "web/assets/fonts/AlbertSans-Regular.woff2",
        "demo/build_week_2026/MANIFEST_SHA256.json",
        "demo/campaign_01_2026/campaign_01.json",
        "demo/showcase_2026/manifest.json",
    ):
        assert (packaged / relative).exists(), relative


def test_build_configuration_includes_nested_web_and_demo_assets():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    manifest = (ROOT / "MANIFEST.in").read_text(encoding="utf-8")
    for pattern in (
        '"assets/web/assets/fonts/*"',
        '"assets/demo/*/*.json"',
    ):
        assert pattern in pyproject
    assert "recursive-include demo *.json" in manifest
    assert "recursive-include prismora_lab/assets *" in manifest
    assert "recursive-include scripts *.py" in manifest
    assert "VERSIONING.md" in manifest


def test_source_and_packaged_frontend_trees_are_byte_identical():
    source = ROOT / "web"
    packaged = ROOT / "prismora_lab" / "assets" / "web"
    source_files = {path.relative_to(source) for path in source.rglob("*") if path.is_file()}
    packaged_files = {path.relative_to(packaged) for path in packaged.rglob("*") if path.is_file()}
    assert source_files == packaged_files
    for relative in source_files:
        assert (source / relative).read_bytes() == (packaged / relative).read_bytes()


def test_source_and_packaged_schema_and_demo_trees_are_byte_identical():
    for source, packaged in (
        (ROOT / "schemas", ROOT / "prismora_lab" / "assets" / "schemas"),
        (ROOT / "demo", ROOT / "prismora_lab" / "assets" / "demo"),
    ):
        source_files = {path.relative_to(source) for path in source.rglob("*") if path.is_file()}
        packaged_files = {path.relative_to(packaged) for path in packaged.rglob("*") if path.is_file()}
        assert source_files == packaged_files
        for relative in source_files:
            assert (source / relative).read_bytes() == (packaged / relative).read_bytes()
