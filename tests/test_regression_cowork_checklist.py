"""
Tests de régression — défauts (b) provenance, (c) hash live-chat, (e) baseline_id, (i) ex æquo.
Audit croisé Opus/Pepper 12/08 · rapport Cowork 08 (27/08) · checklist rejouée 28/08 sur 53e5946.

Chaque test encode le CONTRAT ATTENDU après correctif. Sur un checkout non corrigé, ils échouent
avec un message qui décrit le défaut. Déposer dans tests/ (nom : test_regression_cowork_checklist.py).
Le test (a) traversal est dans test_regression_run_id_traversal.py.
"""
from __future__ import annotations

import asyncio
import copy

from prismora_lab.analysis.baseline import build_top1_reference_distribution
from prismora_lab.analysis.compare import strict_comparison_facts
from prismora_lab.backends.mock import MockBackend
from prismora_lab.canonical import sha256_json
from prismora_lab.normalize import create_run_artifact
from prismora_lab.store import LabStore


def _request(revision: str | None = None) -> dict:
    model = {"alias": "M", "model_id": "mock/12-layer-lab-model"}
    if revision is not None:
        model["revision"] = revision
    return {
        "backend": "mock",
        "model": model,
        "prompt_id": "p",
        "prompt": "x^2 - 5x + 6 = 0",
        "factors": {},
        "repeat": 1,
        "generation": {"temperature": 0, "max_new_tokens": 4},
        "readout": {"types": ["JACOBIAN_LENS"], "top_k": 4, "filter_nonword_tokens": True},
        "intervention": None,
    }


def _raw(request: dict) -> dict:
    return asyncio.run(MockBackend().run(request)).value


def _artifact(tmp_path, run_id: str, request: dict, raw: dict) -> dict:
    return create_run_artifact(store=LabStore(tmp_path), experiment_id="reg", run_id=run_id,
                               request=request, raw=raw, raw_format="mock-json")


# ---- (b) provenance : la révision déclarée dans la requête ne doit pas primer sur celle observée ----
def test_b_declared_revision_mismatch_is_not_silently_recorded(tmp_path):
    request = _request(revision="DECLARED-abc")
    raw = _raw(request)
    raw["meta"]["model_revision"] = "OBSERVED-xyz"  # ce que le worker publie réellement
    art = _artifact(tmp_path, "run-b-0001", request, raw)
    prov = art["provenance"]
    recorded = prov.get("model_revision")
    observed = prov.get("observed", {}).get("model_revision") if isinstance(prov.get("observed"), dict) else None
    warned = any("revision" in str(w).lower() for w in art.get("quality", {}).get("warnings", []))
    mismatch_flag = prov.get("revision_mismatch") is True
    assert recorded == "OBSERVED-xyz" or observed == "OBSERVED-xyz" or warned or mismatch_flag, (
        f"provenance.model_revision = {recorded!r} recopié depuis la requête ; raw.meta dit OBSERVED-xyz ; "
        f"aucun warning ni drapeau revision_mismatch"
    )


# ---- (c) hash live-chat : la normalisation appliquée en production doit être hashée après transformation ----
def test_c_live_chat_normalization_is_hashed_after_transform(tmp_path):
    from prismora_lab import live_chat

    request = _request()
    raw = _raw(request)
    art = create_run_artifact(store=LabStore(tmp_path), experiment_id="regression-c", run_id="run-c-0001",
                              request=request, raw=raw, raw_format="mock-json",
                              artifact_transform=live_chat._normalize_visible_final)
    res = art["result"]
    recomputed = sha256_json({"meta": res["meta"], "tokens": res["tokens"], "done": res["done"]})
    assert art["provenance"]["canonical_result_sha256"] == recomputed, (
        f"hash stocké {art['provenance']['canonical_result_sha256'][:12]}… ≠ hash du result normalisé {recomputed[:12]}…"
    )


# ---- (e) baseline_id : max_tokens_per_layer change la sortie, donc doit changer l'identité ----
def test_e_baseline_id_depends_on_max_tokens_per_layer(tmp_path):
    request = _request()
    art = _artifact(tmp_path, "run-e-0001", request, _raw(request))
    b1 = build_top1_reference_distribution([art], lens="JACOBIAN_LENS", max_tokens_per_layer=1)
    b2 = build_top1_reference_distribution([art], lens="JACOBIAN_LENS", max_tokens_per_layer=30)
    assert b1["baseline_id"] != b2["baseline_id"], (
        f"deux baselines à contenu différent portent le même id {b1['baseline_id']}"
    )


# ---- (i) ex æquo : une permutation de candidats à probabilités identiques n'est pas une divergence ----
def test_i_tied_top1_permutation_is_not_a_top1_divergence(tmp_path):
    request = _request()
    raw_a = _raw(request)
    raw_b = copy.deepcopy(raw_a)
    # Forcer un ex æquo strict sur la première cellule : deux candidats, même probabilité, ordre permuté.
    for raw in (raw_a, raw_b):
        cell = raw["tokens"][0]["results"][0]
        cell["top_tokens"][0] = [" alpha", " beta"] + list(cell["top_tokens"][0][2:])
        probs = list(cell["top_probs"][0])
        probs[0] = probs[1] = 0.25
        cell["top_probs"][0] = probs
    cb = raw_b["tokens"][0]["results"][0]
    cb["top_tokens"][0][0], cb["top_tokens"][0][1] = cb["top_tokens"][0][1], cb["top_tokens"][0][0]

    a = _artifact(tmp_path / "a", "run-i-a-0001", request, raw_a)
    b = _artifact(tmp_path / "b", "run-i-b-0001", request, raw_b)
    facts = strict_comparison_facts(a, b, "JACOBIAN_LENS")
    layer0 = facts["per_layer"][0]
    ambiguous = facts.get("ambiguous_top1_cells")
    assert facts["first_top1_divergence"] is None or ambiguous, (
        f"ex æquo permuté compté comme divergence top-1 : first_top1_divergence={facts['first_top1_divergence']}, "
        f"top1_divergence_rate couche {layer0['layer']} = {layer0['top1_divergence_rate']} ; aucun compteur ambiguous_top1_cells"
    )
