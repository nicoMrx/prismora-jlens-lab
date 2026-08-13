from __future__ import annotations

import copy
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from prismora_lab.campaign_store import campaign_path, save_campaign
from prismora_lab.canonical import atomic_write_bytes, canonical_json_bytes, sha256_json
from prismora_lab.identifiers import IdentifierError
from prismora_lab.normalize import RawShapeError, create_run_artifact
from prismora_lab.preregistration import lock_spec
from prismora_lab.store import LabStore


def request() -> dict:
    return {
        "backend": "mock",
        "model": {"alias": "M01", "model_id": "mock/12-layer-lab-model"},
        "prompt_id": "p1",
        "prompt": "hello",
        "factors": {},
        "repeat": 1,
        "generation": {"temperature": 0, "max_new_tokens": 1},
        "readout": {"types": ["JACOBIAN_LENS"], "top_k": 1, "filter_nonword_tokens": True},
        "intervention": None,
    }


def raw(token: str = "hello", token_id: int = 1) -> dict:
    return {
        "meta": {
            "mock": True,
            "types": ["JACOBIAN_LENS"],
            "layers_by_type": {"JACOBIAN_LENS": [0]},
        },
        "tokens": [
            {
                "position": 0,
                "token": token,
                "id": token_id,
                "is_generated": False,
                "results": [
                    {
                        "type": "JACOBIAN_LENS",
                        "top_tokens": [[token]],
                        "top_probs": [[1.0]],
                    }
                ],
            }
        ],
        "done": {"completion": ""},
    }


def test_storage_identifiers_fail_closed_without_sanitizing(tmp_path):
    store = LabStore(tmp_path)
    for value in ("../escape", "..\\escape", "/absolute", "contains/slash", "wild*card"):
        with pytest.raises(IdentifierError):
            store.experiment_dir(value)
        with pytest.raises(IdentifierError):
            store.run_dir("safe-exp", value)
        with pytest.raises(IdentifierError):
            store.claim_path(value)
        with pytest.raises(IdentifierError):
            campaign_path(store, value)
    assert not (tmp_path.parent / "escape").exists()


def test_raw_bytes_and_parsed_raw_must_match_before_any_write(tmp_path):
    store = LabStore(tmp_path)
    with pytest.raises(RawShapeError, match="does not match"):
        create_run_artifact(
            store=store,
            experiment_id="safe-exp",
            run_id="run-0001",
            request=request(),
            raw=raw("parsed", 1),
            raw_bytes=canonical_json_bytes(raw("bytes", 2)),
            raw_format="mock-json",
        )
    assert not store.run_dir("safe-exp", "run-0001").exists()


def test_invalid_coverage_cannot_leave_an_orphan_raw(tmp_path):
    store = LabStore(tmp_path)
    invalid = raw()
    invalid["coverage"] = {
        "source_tokens_total": 2,
        "transmitted_tokens": 2,
        "instrumented_tokens": 1,
        "instrumented_generated_tokens": 0,
        "truncated_tokens": 0,
        "source_messages_total": 1,
        "transmitted_messages": 1,
        "context_window_limit": None,
        "truncated_message_indices": [],
        "capture_mode": "invalid-test",
        "requested_layers": [0],
        "captured_layers": [0],
        "status": "complete",
        "warnings": [],
    }
    with pytest.raises(ValueError, match="every transmitted context token"):
        create_run_artifact(
            store=store,
            experiment_id="safe-exp",
            run_id="run-0002",
            request=request(),
            raw=invalid,
            raw_format="mock-json",
        )
    assert not store.run_dir("safe-exp", "run-0002").exists()


def test_atomic_create_if_absent_has_exactly_one_concurrent_winner(tmp_path):
    destination = tmp_path / "published.bin"
    workers = 8
    barrier = threading.Barrier(workers)

    def publish(index: int) -> tuple[str, bytes]:
        payload = f"writer-{index}".encode()
        barrier.wait()
        try:
            atomic_write_bytes(destination, payload, overwrite=False)
            return "ok", payload
        except FileExistsError:
            return "exists", payload

    with ThreadPoolExecutor(max_workers=workers) as pool:
        outcomes = list(pool.map(publish, range(workers)))
    winners = [payload for status, payload in outcomes if status == "ok"]
    assert len(winners) == 1
    assert destination.read_bytes() == winners[0]


def test_concurrent_run_publication_never_mixes_raw_and_artifact(tmp_path):
    store = LabStore(tmp_path)
    barrier = threading.Barrier(2)

    def publish(value: dict) -> str:
        barrier.wait()
        try:
            create_run_artifact(
                store=store,
                experiment_id="safe-exp",
                run_id="run-0003",
                request=request(),
                raw=value,
                raw_format="mock-json",
            )
            return "ok"
        except FileExistsError:
            return "exists"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(publish, [raw("left", 1), raw("right", 2)]))
    assert sorted(outcomes) == ["exists", "ok"]
    artifact = store.get_run("run-0003", "safe-exp")
    stored_raw = json.loads((store.run_dir("safe-exp", "run-0003") / "raw.json").read_bytes())
    assert artifact["result"] == {
        "meta": stored_raw["meta"], "tokens": stored_raw["tokens"], "done": stored_raw["done"]
    }
    assert artifact["provenance"]["canonical_result_sha256"] == sha256_json(artifact["result"])


def test_locked_experiment_and_campaign_are_immutable_in_store_api(tmp_path):
    root = Path(__file__).resolve().parents[1]
    spec = json.loads((root / "examples" / "strategy_quadratic_mock.json").read_text())
    store = LabStore(tmp_path)
    store.save_experiment(spec)
    store.save_experiment(lock_spec(spec))
    amended = copy.deepcopy(spec)
    amended["title"] = "Different but internally valid locked document"
    amended = lock_spec(amended)
    with pytest.raises(FileExistsError):
        store.save_experiment(amended)

    campaign = {"campaign_id": "safe-campaign", "title": "locked", "preregistration": {"status": "locked"}}
    save_campaign(store, campaign)
    changed = {**campaign, "title": "changed"}
    with pytest.raises(FileExistsError):
        save_campaign(store, changed)


def test_reads_reject_tampered_internal_hashes(tmp_path):
    store = LabStore(tmp_path)
    artifact = create_run_artifact(
        store=store,
        experiment_id="safe-exp",
        run_id="run-0004",
        request=request(),
        raw=raw(),
        raw_format="mock-json",
    )
    path = store.run_dir("safe-exp", "run-0004") / "artifact.json"
    tampered = copy.deepcopy(artifact)
    tampered["result"]["done"]["completion"] = "tampered"
    path.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(ValueError, match="canonical_result_sha256"):
        store.get_run("run-0004", "safe-exp")


def test_artifact_raw_path_cannot_escape_the_store(tmp_path):
    store = LabStore(tmp_path)
    artifact = create_run_artifact(
        store=store,
        experiment_id="safe-exp",
        run_id="run-0005",
        request=request(),
        raw=raw(),
        raw_format="mock-json",
    )
    escaped = copy.deepcopy(artifact)
    escaped["run_id"] = "run-0006"
    escaped["raw"]["relative_path"] = "../outside/raw.json"
    with pytest.raises(ValueError, match="escapes the store root"):
        store.save_run(escaped)
    assert not store.run_dir("safe-exp", "run-0006").exists()
