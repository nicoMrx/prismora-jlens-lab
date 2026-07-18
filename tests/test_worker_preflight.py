from __future__ import annotations

from prismora_worker.preflight import collect_preflight


def test_preflight_reports_pins_without_loading(monkeypatch):
    monkeypatch.setenv("PRISMORA_HF_MODEL_ID", "org/model")
    monkeypatch.setenv("PRISMORA_HF_MODEL_REVISION", "model-commit")
    monkeypatch.setenv("PRISMORA_HF_TOKENIZER_REVISION", "tokenizer-commit")
    monkeypatch.setenv("PRISMORA_JLENS_NAME_OR_PATH", "org/lens")
    monkeypatch.setenv("PRISMORA_JLENS_REVISION", "lens-commit")
    monkeypatch.setenv("PRISMORA_HF_ALLOW_CPU", "true")

    report = collect_preflight(probe_imports=False)

    assert report["ok"] is True
    assert report["configuration"]["model_revision"] == "model-commit"
    assert not report["warnings"]
