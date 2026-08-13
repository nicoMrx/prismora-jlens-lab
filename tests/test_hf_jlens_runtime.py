from __future__ import annotations

import pytest
from types import SimpleNamespace

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
    assert not HFJacobianLensRuntime._is_word_like("<|assistant|>")
    assert not HFJacobianLensRuntime._is_word_like("<end_of_turn>")


@pytest.mark.parametrize(
    "name,value",
    [
        ("PRISMORA_HF_MAX_INPUT_TOKENS", "0"),
        ("PRISMORA_HF_MAX_NEW_TOKENS", "-1"),
        ("PRISMORA_HF_MAX_TOP_K", "not-an-int"),
    ],
)
def test_hf_jlens_config_rejects_invalid_positive_limits(monkeypatch, name, value):
    monkeypatch.setenv("PRISMORA_HF_MODEL_ID", "org/model")
    monkeypatch.setenv("PRISMORA_HF_MODEL_REVISION", "model-commit")
    monkeypatch.setenv("PRISMORA_HF_TOKENIZER_REVISION", "tokenizer-commit")
    monkeypatch.setenv("PRISMORA_JLENS_NAME_OR_PATH", "org/lens")
    monkeypatch.setenv("PRISMORA_JLENS_REVISION", "lens-commit")
    monkeypatch.setenv(name, value)
    with pytest.raises(RuntimeConfigurationError, match="positive integer"):
        HFJLENSConfig.from_env()


def test_hf_jlens_config_requires_revisions_for_remote_sources(monkeypatch):
    monkeypatch.setenv("PRISMORA_HF_MODEL_ID", "org/model")
    monkeypatch.delenv("PRISMORA_HF_MODEL_REVISION", raising=False)
    monkeypatch.delenv("PRISMORA_HF_TOKENIZER_REVISION", raising=False)
    monkeypatch.setenv("PRISMORA_JLENS_NAME_OR_PATH", "org/lens")
    monkeypatch.delenv("PRISMORA_JLENS_REVISION", raising=False)
    with pytest.raises(RuntimeConfigurationError, match="MODEL_REVISION"):
        HFJLENSConfig.from_env()


def _config() -> HFJLENSConfig:
    return HFJLENSConfig(
        model_id="org/model",
        model_revision="model-commit",
        tokenizer_revision="tokenizer-commit",
        lens_name_or_path="org/lens",
        lens_filename="lens.pt",
        lens_revision="lens-commit",
        dtype="bf16",
        device_map=None,
        trust_remote_code=False,
        force_bos=True,
        allow_cpu=True,
        max_input_tokens=16,
        max_new_tokens=8,
        max_top_k=4,
        attn_implementation=None,
    )


def _request() -> dict:
    return {
        "model": {
            "model_id": "org/model",
            "revision": "model-commit",
            "tokenizer_revision": "tokenizer-commit",
            "lens_id": "org/lens",
            "lens_revision": "lens-commit",
            "precision": "bfloat16",
            "quantization": None,
        },
        "prompt": "hello",
        "generation": {
            "temperature": 0,
            "max_new_tokens": 1,
            "seed": 1,
            "prepend_bos": True,
            "enable_thinking": False,
            "frequency_penalty": 0,
        },
        "readout": {
            "types": ["JACOBIAN_LENS"],
            "top_k": 2,
            "filter_nonword_tokens": True,
            "exclude_first_n_positions": 0,
        },
        "intervention": None,
    }


def test_worker_rejects_false_declared_revisions_and_unsupported_cache():
    runtime = object.__new__(HFJacobianLensRuntime)
    runtime.config = _config()
    request = _request()
    request["model"]["revision"] = "false-claim"
    with pytest.raises(ValueError, match="does not match pinned"):
        runtime._validate_request(request)
    request = _request()
    request["readout"]["cached_token_ids"] = [1]
    with pytest.raises(ValueError, match="cached_token_ids is unsupported"):
        runtime._validate_request(request)


@pytest.mark.parametrize("ids", [[True], [-1], [10]])
def test_forced_token_ids_are_validated_before_tensor_or_gpu_use(ids):
    runtime = object.__new__(HFJacobianLensRuntime)
    runtime.config = _config()
    runtime.vocab_size = 10
    runtime.torch = object()
    runtime.model = SimpleNamespace(input_device="cuda")
    with pytest.raises(ValueError, match="integer array|outside vocabulary"):
        runtime._input_ids({"readout": {"input_token_ids": ids}})


def test_requested_layers_reject_floats_instead_of_truncating_them():
    runtime = object.__new__(HFJacobianLensRuntime)
    runtime.model = SimpleNamespace(n_layers=4)
    runtime.lens = SimpleNamespace(source_layers=[0, 1, 2, 3])
    with pytest.raises(ValueError, match="integer array"):
        runtime._validated_layers([1.5], ["JACOBIAN_LENS"])
