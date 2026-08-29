from __future__ import annotations

import copy, json, zipfile
from pathlib import Path

import pytest

from prismora_lab.analysis.baseline import build_top1_reference_distribution
from prismora_lab.analysis.compare import strict_comparison_facts
from prismora_lab.canonical import sha256_json
from prismora_lab.normalize import create_run_artifact
from prismora_lab.store import LabStore


def _request():
    return {
        "backend":"mock",
        "model":{"alias":"M01","model_id":"mock/model","revision":"DECLARED-model","tokenizer_revision":"DECLARED-tokenizer","lens_id":"lens","lens_revision":"DECLARED-lens"},
        "prompt_id":"p1","prompt":"hello","factors":{},"repeat":1,
        "generation":{"temperature":0,"max_new_tokens":1},
        "readout":{"types":["JACOBIAN_LENS"],"top_k":2,"filter_nonword_tokens":True},
        "intervention":None,
    }


def _raw(run_token="a", probs=None, candidates=None):
    probs = probs or [0.6,0.4]; candidates = candidates or ["A","B"]
    return {
        "meta":{"types":["JACOBIAN_LENS"],"layers_by_type":{"JACOBIAN_LENS":[0]},"model_revision":"OBSERVED-model","tokenizer_revision":"OBSERVED-tokenizer","lens_revision":"OBSERVED-lens"},
        "tokens":[{"position":0,"token":run_token,"id":1,"is_generated":True,"results":[{"type":"JACOBIAN_LENS","top_tokens":[candidates],"top_probs":[probs]}]}],
        "done":{"completion":run_token},
    }


def test_observed_revisions_override_declared_but_both_are_kept(tmp_path):
    store=LabStore(tmp_path)
    a=create_run_artifact(store=store,experiment_id="safe-exp",run_id="run-0001",request=_request(),raw=_raw(),raw_format="mock-json")
    p=a["provenance"]
    assert p["model_revision"]=="OBSERVED-model"
    assert p["tokenizer_revision"]=="OBSERVED-tokenizer"
    assert p["lens_revision"]=="OBSERVED-lens"
    assert p["declared_revisions"]["model_revision"]=="DECLARED-model"
    assert p["observed_revisions"]["model_revision"]=="OBSERVED-model"


def test_locked_schema_requires_spec_sha256(tmp_path):
    root=Path(__file__).resolve().parents[1]
    spec=json.loads((root/"examples/strategy_quadratic_mock.json").read_text())
    spec["preregistration"]={"status":"locked","locked_at":None,"spec_sha256":None,"amendments":[]}
    with pytest.raises(Exception):
        LabStore(tmp_path).save_experiment(spec)


def test_baseline_id_depends_on_max_tokens_per_layer(tmp_path):
    store=LabStore(tmp_path)
    a=create_run_artifact(store=store,experiment_id="safe-exp",run_id="run-0002",request=_request(),raw=_raw(),raw_format="mock-json")
    b1=build_top1_reference_distribution([a],lens="JACOBIAN_LENS",max_tokens_per_layer=1)
    b2=build_top1_reference_distribution([a],lens="JACOBIAN_LENS",max_tokens_per_layer=30)
    assert b1["baseline_id"] != b2["baseline_id"]


def test_derived_records_do_not_overwrite_different_content(tmp_path):
    store=LabStore(tmp_path)
    store.save_derived("safe-exp","baselines","same",{"v":1})
    with pytest.raises(FileExistsError):
        store.save_derived("safe-exp","baselines","same",{"v":2})


def test_top1_tie_permutation_is_not_divergence(tmp_path):
    store=LabStore(tmp_path)
    a=create_run_artifact(store=store,experiment_id="safe-exp",run_id="run-0003",request=_request(),raw=_raw("a",[0.25,0.25],["A","B"]),raw_format="mock-json")
    req=copy.deepcopy(_request()); req["prompt"]="hello2"
    b=create_run_artifact(store=store,experiment_id="safe-exp",run_id="run-0004",request=req,raw=_raw("a",[0.25,0.25],["B","A"]),raw_format="mock-json")
    facts=strict_comparison_facts(a,b,"JACOBIAN_LENS",scope="generated_ordinal")
    assert facts["per_layer"][0]["top1_divergence_rate"] == 0


def test_public_bundle_excludes_live_chat_artifact_and_raw(tmp_path):
    root=Path(__file__).resolve().parents[1]
    store=LabStore(tmp_path)
    spec=json.loads((root/"examples/strategy_quadratic_mock.json").read_text())
    spec["experiment_id"]="safe-exp"
    store.save_experiment(spec)
    a=create_run_artifact(store=store,experiment_id="safe-exp",run_id="run-0005",request=_request(),raw=_raw(),raw_format="mock-json",artifact_transform=lambda x:x.setdefault("derived",{}).__setitem__("live_chat",{"user_message":"private"}))
    z=store.build_bundle("safe-exp")
    with zipfile.ZipFile(z) as archive:
        names=set(archive.namelist())
        manifest=json.loads(archive.read("MANIFEST.json"))
    assert not any("run-0005" in n for n in names)
    assert "run-0005" in manifest["privacy"]["excluded_live_chat_runs"]
