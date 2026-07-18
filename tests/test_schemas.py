import json
from pathlib import Path

from prismora_lab.matrix import expand_experiment
from prismora_lab.schema import validate


EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def test_all_experiment_examples_validate_and_expand():
    counts = {}
    for path in EXAMPLES.glob("*.json"):
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("schema") != "prismora.experiment/v2":
            continue
        validate("experiment", value)
        counts[path.name] = len(expand_experiment(value))
    assert counts["strategy_quadratic_mock.json"] == 3
    assert counts["strategy_quadratic_01.json"] == 54
    assert counts["filter_nonword_bootstrap.json"] == 1
