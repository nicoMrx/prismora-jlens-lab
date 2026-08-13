import json
from pathlib import Path

import copy

import pytest

from prismora_lab.matrix import MatrixError, expand_experiment


ROOT = Path(__file__).resolve().parents[1]


def test_run_ids_are_deterministic_and_bindings_apply():
    spec = json.loads((ROOT / "examples" / "strategy_quadratic_mock.json").read_text())
    first = expand_experiment(spec)
    second = expand_experiment(spec)
    assert [run.run_id for run in first] == [run.run_id for run in second]
    assert [run.request["factors"]["constant"] for run in first] == [5, 6, 7]
    assert "5" in first[0].request["chat"][0]["content"]


def test_filter_binding_changes_readout_setting():
    spec = json.loads((ROOT / "examples" / "strategy_quadratic_mock.json").read_text())
    spec["experiment_id"] = "binding-test"
    spec["matrix"] = {
        "factors": {"filter_nonword": [False, True]},
        "bindings": {"filter_nonword": "readout.filter_nonword_tokens"},
        "repeats": 1,
    }
    spec["prompts"][0]["chat"][0]["content"] = "test"
    runs = expand_experiment(spec)
    assert [run.request["readout"]["filter_nonword_tokens"] for run in runs] == [False, True]


def test_bound_matrix_values_are_revalidated_after_assignment():
    spec = json.loads((ROOT / "examples" / "strategy_quadratic_mock.json").read_text())
    spec["matrix"] = {
        "factors": {"constant": [5], "invalid_top_k": [0]},
        "bindings": {"invalid_top_k": "readout.top_k"},
        "repeats": 1,
    }
    with pytest.raises(MatrixError, match="Bound request is invalid"):
        expand_experiment(spec)


def test_run_id_is_bounded_even_when_every_valid_component_is_maximal():
    spec = json.loads((ROOT / "examples" / "strategy_quadratic_mock.json").read_text())
    spec = copy.deepcopy(spec)
    spec["experiment_id"] = "e" * 80
    spec["models"][0]["alias"] = "M" * 64
    spec["prompts"][0]["prompt_id"] = "P" * 80
    runs = expand_experiment(spec)
    assert runs
    assert all(8 <= len(run.run_id) <= 160 for run in runs)
