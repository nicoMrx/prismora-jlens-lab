#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from prismora_lab.normalize import create_run_artifact
from prismora_lab.store import LabStore
from prismora_lab.timeutil import utc_now_iso

EXPERIMENT_ID = "probe-jlens-interventions-20260715"

CASES = {
    "T7_jlens_inline_steer_prismora_shape": {
        "run_id": "probe-20260715-steer-factor-l40",
        "condition": "steer_factor_l40",
    },
    "T8_jlens_inline_swap_prismora_shape": {
        "run_id": "probe-20260715-swap-factor-formula-l40",
        "condition": "swap_factor_to_formula_l40",
    },
    "T9_jlens_inline_ablate_prismora_shape": {
        "run_id": "probe-20260715-ablate-factor-l40",
        "condition": "ablate_factor_l40",
    },
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def intervention_from_payload(payload: dict[str, Any]) -> dict[str, Any] | None:
    source = payload.get("steerTokens") or []
    common = {
        "source_tokens": source,
        "layers": payload.get("steerLayers") or [],
        "apply_to_generated_tokens": bool(payload.get("steerGeneratedTokens")),
    }
    if payload.get("steerAblate"):
        return {"mode": "ablate", **common, "target_token": None, "strength": None}
    if payload.get("swapToken"):
        return {
            "mode": "swap",
            **common,
            "target_token": payload.get("swapToken"),
            "strength": payload.get("steerStrength"),
        }
    if source:
        return {
            "mode": "steer",
            **common,
            "target_token": None,
            "strength": payload.get("steerStrength"),
        }
    return None


def make_spec() -> dict[str, Any]:
    return {
        "schema": "prismora.experiment/v2",
        "experiment_id": EXPERIMENT_ID,
        "title": "Probe exploratoire — interventions J-Lens du 15 juillet 2026",
        "description": (
            "Import visuel des réponses exactes T7/T8/T9 du probe exploratoire. "
            "Ce protocole est historique et reste draft : il n'est pas rebaptisé "
            "rétroactivement comme préenregistré."
        ),
        "tags": ["probe", "neuronpedia", "j-lens", "steer", "swap", "ablate"],
        "hypothesis": {
            "primary": "Tester si les champs d'intervention J-Lens sont appliqués par l'API publique.",
            "falsifiers": [
                "Les réponses sont identiques à une requête sans intervention.",
                "Les divergences apparaissent avant la couche déclarée.",
                "Les champs sont acceptés mais n'altèrent aucun read-out ni token généré.",
            ],
            "exploratory": ["Localiser la première divergence par couche."],
        },
        "preregistration": {
            "status": "draft",
            "locked_at": None,
            "spec_sha256": None,
            "amendments": [],
        },
        "models": [
            {
                "alias": "Q36",
                "model_id": "qwen3.6-27b",
                "backend": "neuronpedia",
                "blind_alias": "Q36",
                "organization": "Qwen",
                "origin_region": "China",
                "model_type": "instruct",
                "revision": None,
                "tokenizer_revision": None,
                "lens_id": "Neuronpedia public J-Lens",
                "lens_revision": None,
                "precision": None,
                "quantization": None,
                "metadata": {"historical_import": True},
            }
        ],
        "prompts": [
            {
                "prompt_id": "quadratic_probe",
                "prompt": "Solve x^2 - 5x + 6 = 0. Show only algebraic transformations and roots.",
                "metadata": {"historical_probe": True},
            }
        ],
        "matrix": {"factors": {"condition": ["steer", "swap", "ablate"]}, "bindings": {}, "repeats": 1},
        "generation": {
            "temperature": 0,
            "max_new_tokens": 24,
            "seed": None,
            "prepend_bos": True,
            "enable_thinking": False,
            "frequency_penalty": 0,
        },
        "readout": {
            "types": ["JACOBIAN_LENS", "LOGIT_LENS"],
            "top_k": 8,
            "filter_nonword_tokens": True,
            "exclude_first_n_positions": 0,
        },
        "analysis": {
            "primary_metric": "first_readout_divergence_layer",
            "secondary_metrics": ["generated_surface_change", "top1_agreement_by_layer", "topk_jaccard"],
            "exclusions": [],
            "compare_absolute_and_relative_depth": True,
            "semantic_families": {},
            "generated_positions_only": False,
            "presence_min_probability": 0.01,
            "notes": "Exploratory import for human visual control.",
        },
        "stopping_rule": "Historical import only; no new calls are made.",
        "metadata": {
            "imported_at": utc_now_iso(),
            "source_probe": "probe_20260715T074434Z",
            "historical_exploratory": True,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe-dir", required=True)
    parser.add_argument("--data-dir", required=True)
    args = parser.parse_args()

    probe_dir = Path(args.probe_dir).expanduser().resolve()
    data_dir = Path(args.data_dir).expanduser().resolve()
    if not probe_dir.is_dir():
        raise SystemExit(f"Dossier probe introuvable : {probe_dir}")

    store = LabStore(data_dir)
    store.save_experiment(make_spec())
    imported: list[dict[str, Any]] = []

    for base, info in CASES.items():
        request_path = probe_dir / f"{base}_request_exact.json"
        raw_path = probe_dir / f"{base}_response_exact.raw"
        if not request_path.exists() or not raw_path.exists():
            raise SystemExit(f"Fichiers manquants pour {base}")
        request_bytes = request_path.read_bytes()
        raw_bytes = raw_path.read_bytes()
        api_request = json.loads(request_bytes.decode("utf-8"))
        raw = json.loads(raw_bytes.decode("utf-8"))
        intervention = intervention_from_payload(api_request)
        request = {
            "backend": "neuronpedia",
            "model": {
                "alias": "Q36",
                "model_id": api_request.get("modelId", "qwen3.6-27b"),
                "revision": None,
                "tokenizer_revision": None,
                "lens_id": "Neuronpedia public J-Lens",
                "lens_revision": None,
                "precision": None,
                "quantization": None,
            },
            "prompt_id": "quadratic_probe",
            "prompt": api_request.get("prompt", ""),
            "factors": {"probe_test": base.split("_", 1)[0], "condition": info["condition"]},
            "repeat": 1,
            "generation": {
                "temperature": api_request.get("temperature", 0),
                "max_new_tokens": api_request.get("numCompletionTokens", 0),
                "seed": None,
                "prepend_bos": api_request.get("prependBos", True),
                "enable_thinking": api_request.get("enableThinking", False),
                "frequency_penalty": 0,
            },
            "readout": {
                "types": api_request.get("type", []),
                "top_k": api_request.get("topN", 8),
                "filter_nonword_tokens": api_request.get("filterNonWordTokens", True),
            },
            "intervention": intervention,
            "probe_provenance": {
                "test_name": base,
                "exact_request_sha256": sha256_bytes(request_bytes),
                "exact_response_sha256": sha256_bytes(raw_bytes),
            },
        }
        artifact = create_run_artifact(
            store=store,
            experiment_id=EXPERIMENT_ID,
            run_id=info["run_id"],
            request=request,
            raw=raw,
            raw_format="imported-json",
            raw_bytes=raw_bytes,
            raw_content_type="application/json",
            backend_environment={
                "historical_probe_import": True,
                "probe_test_name": base,
                "exact_request_sha256": sha256_bytes(request_bytes),
            },
        )
        derived_dir = store.experiment_dir(EXPERIMENT_ID) / "derived" / "probe_requests"
        derived_dir.mkdir(parents=True, exist_ok=True)
        exact_request_copy = derived_dir / f"{info['run_id']}.request_exact.json"
        if exact_request_copy.exists() and exact_request_copy.read_bytes() != request_bytes:
            raise SystemExit(f"Une requête exacte différente existe déjà : {exact_request_copy}")
        exact_request_copy.write_bytes(request_bytes)
        imported.append({
            "run_id": artifact["run_id"],
            "condition": info["condition"],
            "raw_sha256": artifact["provenance"]["raw_sha256"],
            "request_exact_sha256": sha256_bytes(request_bytes),
        })

    report = {
        "experiment_id": EXPERIMENT_ID,
        "data_dir": str(data_dir),
        "probe_dir": str(probe_dir),
        "imported": imported,
    }
    report_path = store.experiment_dir(EXPERIMENT_ID) / "derived" / "probe_import_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
