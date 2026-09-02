"""Contract test for prismora_worker.interp_engine_runtime with fakes.

Proves, without CUDA or any checkpoint, that the runtime honours the worker
return contract ({meta, tokens, done, coverage}), declares engine/compute_path/
lens_sha256, replays exact token IDs, applies the lens on the Jacobian type
only (J = I on the final layer), and keeps the incremental-path truncation
honest. It does NOT prove numerical parity -- that is the bridge validation.
"""
from __future__ import annotations

import asyncio
import types

from prismora_worker.hf_jlens_runtime import HFJLENSConfig
from prismora_worker.interp_engine_runtime import InterpEngineJLensRuntime, _ModelFacts

VOCAB, D, N_LAYERS = 12, 4, 3


class FakeTensor:
    """Tiny tensor stand-in sufficient for this contract test."""

    def __init__(self, data):
        self.data = data

    @property
    def shape(self):
        if isinstance(self.data, list):
            if self.data and isinstance(self.data[0], list):
                return (len(self.data), len(self.data[0]))
            return (len(self.data),)
        return ()

    def __getitem__(self, item):
        value = self.data[item]
        return FakeTensor(value) if isinstance(value, list) else value

    def tolist(self):
        return self.data if isinstance(self.data, list) else [self.data]

    def float(self):
        return self

    def cpu(self):
        return self

    def __mul__(self, _other):
        return self


class FakeTorch:
    long = "long"

    @staticmethod
    def tensor(data, **_kwargs):
        return FakeTensor(data)

    @staticmethod
    def full(shape, value):
        rows, cols = shape
        return FakeTensor([[value for _ in range(cols)] for _ in range(rows)])


torch = FakeTorch()


class FakeTokenizer:
    vocab_size = VOCAB
    bos_token_id = 0
    eos_token_id = 1
    pad_token_id = 1

    def decode(self, ids, **_):
        return "".join(f"t{i}" for i in ids)

    def __call__(self, text, **_):
        ids = [ord(c) % (VOCAB - 2) + 2 for c in text]
        return types.SimpleNamespace(input_ids=torch.tensor([ids]))


class FakeEngine:
    n_layers = N_LAYERS
    d_model = D

    def __init__(self):
        self.warmed = False
        self.calls: list[str] = []

    async def warmup(self):
        self.warmed = True

    async def capture_generation(self, prompt_ids, points, *, max_tokens, temperature, seed):
        self.calls.append(f"capture_generation:{len(points)}")
        gen = [3, 4][:max_tokens]
        rows = {}
        n = len(prompt_ids) + len(gen) - 1
        for p in points:
            layer = int(p.split(".")[1])
            rows[p] = torch.full((n, D), float(layer))
        return types.SimpleNamespace(text="x", token_ids=gen), rows

    async def capture(self, ids, points):
        self.calls.append(f"capture:{len(ids)}")
        return {p: torch.full((len(ids), D), float(p.split('.')[1])) for p in points}

    async def decode_residuals(self, residual):
        return residual


class FakeLens:
    d_model = D
    source_layers = [0, 1, 2]

    def __init__(self):
        self.applied: list[int] = []

    def transport(self, residual, layer):
        self.applied.append(layer)
        return residual * 10


def _runtime(capture_path: str) -> InterpEngineJLensRuntime:
    rt = InterpEngineJLensRuntime.__new__(InterpEngineJLensRuntime)
    rt.config = HFJLENSConfig(
        model_id="fake/model", model_revision="r1", tokenizer_revision="r1",
        lens_name_or_path="fake/lens", lens_filename="lens.pt", lens_revision="r1",
        dtype="bfloat16", device_map=None, trust_remote_code=False, force_bos=True,
        allow_cpu=True, max_input_tokens=64, max_new_tokens=8, max_top_k=8, attn_implementation=None,
    )
    rt.torch = torch
    rt.backend = "eager"
    rt.capture_path = capture_path
    rt.engine_model = FakeEngine()
    rt._warm = False
    rt.model = _ModelFacts(input_device="cpu", n_layers=N_LAYERS, d_model=D)
    rt.tokenizer = FakeTokenizer()
    rt.lens = FakeLens()
    rt.lens_sha256 = "ab" * 32
    rt.lens_shape = [N_LAYERS, D, D]
    rt.expected_lens_shape = [N_LAYERS, D, D]
    rt.vocab_size = VOCAB
    rt._decoded_vocab = None
    rt._word_mask_by_device = {}
    rt.runtime_id = "interp-engine-jlens:test"
    rt.software_versions = {"interp_engine": "test"}
    rt._run_lock = asyncio.Lock()

    def fake_topk(logits, top_k, _filter_nonword):
        rows = int(logits.shape[0])
        ids = [[VOCAB - 1 - rank for rank in range(top_k)] for _ in range(rows)]
        probs = [[1.0 / (rank + 2) for rank in range(top_k)] for _ in range(rows)]
        return FakeTensor(ids), FakeTensor(probs)

    rt._topk = fake_topk
    return rt


def _request(**over):
    req = {
        "model": {"model_id": "fake/model"},
        "generation": {"max_new_tokens": 2, "temperature": 0, "prepend_bos": True},
        "readout": {"top_k": 3, "types": ["JACOBIAN_LENS", "LOGIT_LENS"], "layers": [0, 2],
                    "input_token_ids": [0, 5, 6], "filter_nonword_tokens": False},
    }
    req.update(over)
    return req


def test_recompute_path_contract():
    rt = _runtime("recompute")
    out = asyncio.run(rt.run(_request()))
    assert rt.engine_model.warmed
    assert rt.engine_model.calls == ["capture_generation:0", "capture:5"]
    assert out["meta"]["engine"] == "interp-engine"
    assert out["meta"]["compute_path"] == "recompute"
    assert out["meta"]["lens_sha256"] == "ab" * 32
    assert out["meta"]["exact_token_replay"] is True
    assert [t["id"] for t in out["tokens"]] == [0, 5, 6, 3, 4]
    assert [t["is_generated"] for t in out["tokens"]] == [False, False, False, True, True]
    assert out["done"]["seq_len"] == 5 and out["done"]["prompt_len"] == 3
    assert out["coverage"]["status"] == "complete"
    assert rt.lens.applied == [0]
    for row in out["tokens"]:
        for res in row["results"]:
            assert len(res["top_tokens"]) == 2 and len(res["top_probs"]) == 2
            assert all(len(x) == 3 for x in res["top_tokens"])


def test_incremental_path_declares_truncation():
    rt = _runtime("incremental")
    out = asyncio.run(rt.run(_request()))
    assert rt.engine_model.calls == ["capture_generation:2"]
    assert out["meta"]["compute_path"] == "incremental"
    assert out["coverage"]["truncated_tokens"] == 1
    assert out["coverage"]["status"] == "partial"
    assert out["tokens"][-1]["results"][0]["top_tokens"] == []


def test_rejects_interventions_and_wrong_model():
    rt = _runtime("recompute")
    bad = _request(intervention={"mode": "steer"})
    try:
        asyncio.run(rt.run(bad))
        raise AssertionError("intervention must be rejected")
    except ValueError:
        pass
    wrong = _request(model={"model_id": "other/model"})
    try:
        asyncio.run(rt.run(wrong))
        raise AssertionError("wrong model must be rejected")
    except ValueError:
        pass
