from __future__ import annotations

import copy

from prismora_lab.analysis.compare import bridge_equivalence
from prismora_lab.backends.mock import MockBackend
from prismora_lab.normalize import create_run_artifact
from prismora_lab.store import LabStore


def _artifact(tmp_path, run_id: str, raw: dict):
    store = LabStore(tmp_path)
    request = {
        "backend": "mock",
        "model": {"alias": "M", "model_id": "mock/12-layer-lab-model"},
        "prompt_id": "p",
        "prompt": "x^2 - 5x + 6 = 0",
        "factors": {},
        "repeat": 1,
        "generation": {"temperature": 0, "max_new_tokens": 4},
        "readout": {"types": ["JACOBIAN_LENS"], "top_k": 4, "filter_nonword_tokens": True},
        "intervention": None,
    }
    return create_run_artifact(
        store=store,
        experiment_id="bridge",
        run_id=run_id,
        request=request,
        raw=raw,
        raw_format="mock-json",
    )


def test_bridge_equivalence_identical_and_probability_tolerance(tmp_path):
    import asyncio

    request = {
        "backend": "mock",
        "model": {"alias": "M", "model_id": "mock/12-layer-lab-model"},
        "prompt_id": "p",
        "prompt": "x^2 - 5x + 6 = 0",
        "factors": {},
        "repeat": 1,
        "generation": {"temperature": 0, "max_new_tokens": 4},
        "readout": {"types": ["JACOBIAN_LENS"], "top_k": 4, "filter_nonword_tokens": True},
        "intervention": None,
    }
    raw = asyncio.run(MockBackend().run(request)).value
    a = _artifact(tmp_path / "a", "run-a-0001", raw)
    b = _artifact(tmp_path / "b", "run-b-0001", copy.deepcopy(raw))
    same = bridge_equivalence(a, b, "JACOBIAN_LENS", probability_abs_tolerance=0)
    assert same["equivalent_under_declared_tolerance"] is True

    changed_raw = copy.deepcopy(raw)
    changed_raw["tokens"][0]["results"][0]["top_probs"][0][0] += 0.005
    c = _artifact(tmp_path / "c", "run-c-0001", changed_raw)
    strict = bridge_equivalence(a, c, "JACOBIAN_LENS", probability_abs_tolerance=0.001)
    loose = bridge_equivalence(a, c, "JACOBIAN_LENS", probability_abs_tolerance=0.01)
    assert strict["equivalent_under_declared_tolerance"] is False
    assert loose["equivalent_under_declared_tolerance"] is True
