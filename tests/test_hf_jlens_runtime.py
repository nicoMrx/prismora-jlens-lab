from __future__ import annotations

import pytest

from prismora_worker.hf_jlens_runtime import (
    HFJLENSConfig,
    HFJacobianLensRuntime,
    RuntimeConfigurationError,
)


def test_hf_jlens_config_from_env(monkeypatch):
    monkeypatch.setenv("PRISMORA_HF_MODEL_ID", "org/model")
    monkeypatch.setenv("PRISMORA_HF_MODEL_REVISION", "model-commit")
    monkeypatch.setenv("PRISMORA_JLENS_NAME_OR_PATH", "org/lenses")
    monkeypatch.setenv("PRISMORA_JLENS_FILENAME", "model/lens.pt")
    monkeypatch.setenv("PRISMORA_JLENS_REVISION", "lens-commit")
    monkeypatch.setenv("PRISMORA_HF_DTYPE", "bf16")
    monkeypatch.setenv("PRISMORA_HF_DEVICE_MAP", "auto")
    monkeypatch.setenv("PRISMORA_HF_MAX_INPUT_TOKENS", "1024")
    monkeypatch.setenv("PRISMORA_HF_MAX_NEW_TOKENS", "256")
    monkeypatch.setenv("PRISMORA_HF_MAX_TOP_K", "12")

    config = HFJLENSConfig.from_env()

    assert config.model_id == "org/model"
    assert config.model_revision == "model-commit"
    assert config.tokenizer_revision == "model-commit"
    assert config.lens_name_or_path == "org/lenses"
    assert config.lens_filename == "model/lens.pt"
    assert config.lens_revision == "lens-commit"
    assert config.dtype == "bf16"
    assert config.device_map == "auto"
    assert config.max_input_tokens == 1024
    assert config.max_new_tokens == 256
    assert config.max_top_k == 12


def test_hf_jlens_config_requires_model_and_lens(monkeypatch):
    monkeypatch.delenv("PRISMORA_HF_MODEL_ID", raising=False)
    monkeypatch.delenv("PRISMORA_JLENS_NAME_OR_PATH", raising=False)
    with pytest.raises(RuntimeConfigurationError):
        HFJLENSConfig.from_env()


def test_unicode_word_filter_classifier():
    assert HFJacobianLensRuntime._is_word_like(" formula")
    assert HFJacobianLensRuntime._is_word_like("公式")
    assert HFJacobianLensRuntime._is_word_like("42")
    assert not HFJacobianLensRuntime._is_word_like("   ")
    assert not HFJacobianLensRuntime._is_word_like("\n")
    assert not HFJacobianLensRuntime._is_word_like("...")
