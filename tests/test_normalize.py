import asyncio
import json
from pathlib import Path

from prismora_lab.backends.mock import MockBackend
from prismora_lab.cockpit import to_cockpit_v1
from prismora_lab.matrix import expand_experiment
from prismora_lab.normalize import create_run_artifact
from prismora_lab.protocol_tools import make_filter_replay_spec
from prismora_lab.schema import validate
from prismora_lab.store import LabStore


ROOT = Path(__file__).resolve().parents[1]


def test_raw_is_immutable_and_duplicates_are_not_independent(tmp_path):
    spec = json.loads((ROOT / "examples" / "strategy_quadratic_mock.json").read_text())
    run = expand_experiment(spec)[0]
    backend_result = asyncio.run(MockBackend().run(run.request))
    raw = backend_result.value
    store = LabStore(tmp_path)
    store.save_experiment(spec)
    first = create_run_artifact(store=store, experiment_id=spec["experiment_id"], run_id=run.run_id, request=run.request, raw=raw, raw_format="mock-json", raw_bytes=backend_result.raw_bytes)
    second = create_run_artifact(store=store, experiment_id=spec["experiment_id"], run_id=run.run_id + "-duplicate", request=run.request, raw=raw, raw_format="mock-json", raw_bytes=backend_result.raw_bytes)
    assert first["quality"]["independent_observation"] is True
    assert second["quality"]["independent_observation"] is False
    assert second["quality"]["duplicate_of"] == first["run_id"]
    cockpit = to_cockpit_v1(first)
    assert cockpit["cockpit_schema_version"] == 1
    assert cockpit["tokens"]


def test_filter_replay_uses_exact_token_ids(tmp_path):
    spec = json.loads((ROOT / "examples" / "strategy_quadratic_mock.json").read_text())
    run = expand_experiment(spec)[0]
    backend_result = asyncio.run(MockBackend().run(run.request))
    raw = backend_result.value
    store = LabStore(tmp_path)
    store.save_experiment(spec)
    artifact = create_run_artifact(store=store, experiment_id=spec["experiment_id"], run_id=run.run_id, request=run.request, raw=raw, raw_format="mock-json", raw_bytes=backend_result.raw_bytes)
    replay = make_filter_replay_spec(artifact, experiment_id="exact-filter-replay")
    validate("experiment", replay)
    planned = expand_experiment(replay)
    assert len(planned) == 2
    expected = [token["id"] for token in artifact["result"]["tokens"]]
    assert all(item.request["readout"]["input_token_ids"] == expected for item in planned)
    assert [item.request["readout"]["filter_nonword_tokens"] for item in planned] == [False, True]


def test_empirical_baseline_records_provenance(tmp_path):
    from prismora_lab.analysis.baseline import build_top1_reference_distribution

    spec = json.loads((ROOT / "examples" / "strategy_quadratic_mock.json").read_text())
    store = LabStore(tmp_path)
    store.save_experiment(spec)
    artifacts = []
    for run in expand_experiment(spec)[:2]:
        backend_result = asyncio.run(MockBackend().run(run.request))
        raw = backend_result.value
        artifacts.append(
            create_run_artifact(
                store=store,
                experiment_id=spec["experiment_id"],
                run_id=run.run_id,
                request=run.request,
                raw=raw,
                raw_format="mock-json",
                raw_bytes=backend_result.raw_bytes,
            )
        )
    baseline = build_top1_reference_distribution(artifacts, lens="JACOBIAN_LENS", position_scope="generated")
    assert baseline["run_ids"] == [artifact["run_id"] for artifact in artifacts]
    assert baseline["per_layer"]
    assert baseline["interpretation_limit"]


def test_identical_result_from_different_executable_condition_is_not_collapsed(tmp_path):
    spec = json.loads((ROOT / "examples" / "strategy_quadratic_mock.json").read_text())
    run = expand_experiment(spec)[0]
    backend_result = asyncio.run(MockBackend().run(run.request))
    store = LabStore(tmp_path)
    store.save_experiment(spec)
    first = create_run_artifact(
        store=store,
        experiment_id=spec["experiment_id"],
        run_id=run.run_id,
        request=run.request,
        raw=backend_result.value,
        raw_format="mock-json",
        raw_bytes=backend_result.raw_bytes,
    )
    changed_request = json.loads(json.dumps(run.request))
    changed_request["chat"][0]["content"] += " Different executable prompt."
    second = create_run_artifact(
        store=store,
        experiment_id=spec["experiment_id"],
        run_id=run.run_id + "-different-prompt",
        request=changed_request,
        raw=backend_result.value,
        raw_format="mock-json",
        raw_bytes=backend_result.raw_bytes,
    )
    assert first["quality"]["independent_observation"] is True
    assert second["quality"]["independent_observation"] is True
    assert first["provenance"]["execution_request_sha256"] != second["provenance"]["execution_request_sha256"]
