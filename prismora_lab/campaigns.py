from __future__ import annotations

import re
from collections import Counter
from typing import Any

from .canonical import sha256_json
from .matrix import expand_experiment, plan_summary
from .schema import validate


_SAFE = re.compile(r"[^a-z0-9._-]+")


def _slug(value: Any, *, fallback: str, limit: int = 48) -> str:
    text = str(value or "").strip().lower().replace("_", "-")
    text = _SAFE.sub("-", text).strip("-._")
    if not text:
        text = fallback
    if not text[0].isalnum():
        text = f"x-{text}"
    return text[:limit].rstrip("-._") or fallback


def _cell_value(cell: dict[str, Any], defaults: dict[str, Any], key: str, fallback: Any) -> Any:
    if key in cell:
        return cell[key]
    if key in defaults:
        return defaults[key]
    return fallback


def _model_spec(model_id: str) -> dict[str, Any]:
    alias = _slug(model_id, fallback="model", limit=63)
    return {
        "alias": alias,
        "model_id": model_id,
        "backend": "neuronpedia",
        "blind_alias": None,
        "organization": None,
        "origin_region": None,
        "model_type": "unknown",
        "revision": None,
        "tokenizer_revision": None,
        "lens_id": None,
        "lens_revision": None,
        "precision": None,
        "quantization": None,
        "metadata": {},
    }


def _condition_spec(
    *,
    campaign_id: str,
    condition_index: int,
    condition_id: str,
    design: str,
    repeats: int,
    model_id: str,
    input_kind: str,
    prompt: str,
    domain: str,
    language: str,
    filter_nonword: bool,
    temperature: float,
    max_new_tokens: int,
    prepend_bos: bool,
    enable_thinking: bool,
    top_k: int,
    author: str,
) -> dict[str, Any]:
    experiment_id = f"{campaign_id}-{condition_id}"[:80].rstrip("-._")
    prompt_id = f"p{condition_index:03d}"
    prompt_spec: dict[str, Any] = {"prompt_id": prompt_id, "metadata": {"domain": domain, "language": language}}
    if input_kind == "completion":
        prompt_spec["prompt"] = prompt
    else:
        prompt_spec["chat"] = [{"role": "user", "content": prompt}]

    spec = {
        "schema": "prismora.experiment/v2",
        "experiment_id": experiment_id,
        "title": f"{campaign_id} · {condition_id} · {domain} · {language}",
        "description": design,
        "tags": ["campaign", _slug(domain, fallback="domain", limit=72), _slug(language, fallback="lang", limit=72)],
        "hypothesis": {
            "primary": f"Measure a repeatable J-Lens trajectory for condition {domain}/{language}.",
            "falsifiers": [
                "No candidate or trajectory remains stable beyond the measured infrastructure-noise floor across repetitions."
            ],
            "exploratory": ["Inspect language, domain and filter effects without promoting them to causal claims."],
        },
        "preregistration": {"status": "draft", "locked_at": None, "spec_sha256": None, "amendments": []},
        "models": [_model_spec(model_id)],
        "prompts": [prompt_spec],
        "matrix": {"factors": {}, "bindings": {}, "repeats": repeats},
        "generation": {
            "temperature": temperature,
            "max_new_tokens": max_new_tokens,
            "seed": None,
            "prepend_bos": prepend_bos,
            "enable_thinking": enable_thinking,
            "frequency_penalty": 0,
        },
        "readout": {
            "types": ["JACOBIAN_LENS", "LOGIT_LENS"],
            "top_k": top_k,
            "filter_nonword_tokens": filter_nonword,
            "exclude_first_n_positions": 0,
        },
        "intervention": None,
        "analysis": {
            "primary_metric": "multi-run top-1 consensus",
            "secondary_metrics": ["candidate presence p>=0.01", "absolute and relative depth"],
            "exclusions": ["template and channel-marker positions must be analysed separately from content positions"],
            "compare_absolute_and_relative_depth": True,
            "semantic_families": {},
            "generated_positions_only": False,
            "presence_min_probability": 0.01,
            "notes": "Imported from the Phase 1 Campaign 01 kit. Infrastructure noise requires repeated observations.",
        },
        "stopping_rule": "Complete the planned repetitions unless a safety, quota or infrastructure failure occurs.",
        "metadata": {
            "campaign_id": campaign_id,
            "condition_id": condition_id,
            "legacy_condition_index": condition_index,
            "legacy_domain": domain,
            "legacy_language": language,
            "legacy_filter_nonword": filter_nonword,
            "legacy_input_kind": input_kind,
            "author": author,
            "signature": author,
        },
    }
    validate("experiment", spec)
    return spec


def legacy_campaign_to_plan(
    payload: dict[str, Any],
    *,
    campaign_id: str | None = None,
    author: str = "NicoMrx",
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Legacy campaign root must be an object.")
    cells = payload.get("cells")
    defaults = payload.get("defaults") or {}
    if not isinstance(cells, list) or not cells:
        raise ValueError("Legacy campaign needs a non-empty cells array.")
    if not isinstance(defaults, dict):
        raise ValueError("Legacy campaign defaults must be an object.")

    campaign_id = _slug(campaign_id or payload.get("campaign_id") or "campaign-01", fallback="campaign-01")
    repeats = int(payload.get("repeats", 1))
    if not 1 <= repeats <= 100:
        raise ValueError("Legacy repeats must be in the range 1..100.")
    default_model = str(payload.get("model_id") or "qwen3.6-27b")
    design = str(payload.get("_design") or "Imported legacy Prismora campaign.")

    specs: list[dict[str, Any]] = []
    conditions: list[dict[str, Any]] = []
    condition_index = 0
    estimated_bytes = 0

    for cell_index, cell in enumerate(cells, start=1):
        if not isinstance(cell, dict):
            raise ValueError(f"Cell {cell_index} must be an object.")
        prompts = cell.get("prompts")
        if not isinstance(prompts, list) or not prompts:
            raise ValueError(f"Cell {cell_index} needs prompts[].")
        filters = cell.get("filter_variants", [True])
        if not isinstance(filters, list) or not filters:
            raise ValueError(f"Cell {cell_index} needs filter_variants[].")

        domain = str(cell.get("domain") or f"cell-{cell_index:02d}")
        language = str(cell.get("language") or "unknown")
        model_id = str(cell.get("model_id") or default_model)
        input_kind = str(_cell_value(cell, defaults, "input_kind", "chat"))
        if input_kind not in {"chat", "completion"}:
            raise ValueError(f"Unsupported input_kind {input_kind!r} in cell {cell_index}.")
        temperature = float(_cell_value(cell, defaults, "temperature", 0))
        max_new_tokens = int(_cell_value(cell, defaults, "num_completion_tokens", 64))
        prepend_bos = bool(_cell_value(cell, defaults, "prepend_bos", True))
        enable_thinking = bool(_cell_value(cell, defaults, "enable_thinking", False))
        top_k = int(_cell_value(cell, defaults, "top_n", 8))

        for prompt in prompts:
            if not isinstance(prompt, str) or not prompt.strip():
                raise ValueError(f"Cell {cell_index} contains an empty prompt.")
            for filter_value in filters:
                condition_index += 1
                condition_id = f"c{condition_index:03d}"
                filter_nonword = bool(filter_value)
                spec = _condition_spec(
                    campaign_id=campaign_id,
                    condition_index=condition_index,
                    condition_id=condition_id,
                    design=design,
                    repeats=repeats,
                    model_id=model_id,
                    input_kind=input_kind,
                    prompt=prompt,
                    domain=domain,
                    language=language,
                    filter_nonword=filter_nonword,
                    temperature=temperature,
                    max_new_tokens=max_new_tokens,
                    prepend_bos=prepend_bos,
                    enable_thinking=enable_thinking,
                    top_k=top_k,
                    author=author,
                )
                runs = expand_experiment(spec)
                if len(runs) != repeats:
                    raise ValueError(f"Condition {condition_id} expanded to {len(runs)} runs instead of {repeats}.")
                summary = plan_summary(spec, runs)
                specs.append(spec)
                conditions.append(
                    {
                        "condition_id": condition_id,
                        "experiment_id": spec["experiment_id"],
                        "domain": domain,
                        "language": language,
                        "model_id": model_id,
                        "input_kind": input_kind,
                        "filter_nonword_tokens": filter_nonword,
                        "prompt": prompt,
                        "temperature": temperature,
                        "max_new_tokens": max_new_tokens,
                        "top_k": top_k,
                        "planned_runs": len(runs),
                        "warnings": summary["warnings"],
                    }
                )
                estimated_bytes += int(4_000_000 * max(1, max_new_tokens) / 64) * repeats

    run_count = sum(item["planned_runs"] for item in conditions)
    by_model = Counter(item["model_id"] for item in conditions for _ in range(item["planned_runs"]))
    by_domain = Counter(item["domain"] for item in conditions for _ in range(item["planned_runs"]))
    by_language = Counter(item["language"] for item in conditions for _ in range(item["planned_runs"]))
    warnings = [
        "Campaign is still draft; lock the compiled experiments before describing results as preregistered.",
        "Run a single preflight and a repeated noise-floor check before scaling the complete campaign.",
        "Raw responses are immutable evidence and must never be edited in place.",
    ]

    return {
        "schema": "prismora.campaign/v1",
        "campaign_id": campaign_id,
        "title": "Campagne 01 · Phase 1" if campaign_id == "campaign-01" else campaign_id,
        "description": design,
        "author": author,
        "signature": author,
        "preregistration": {"status": "draft", "locked_at": None},
        "source": {
            "format": "legacy-campaign-json/v1",
            "sha256": sha256_json(payload),
        },
        "condition_count": len(conditions),
        "run_count": run_count,
        "repeats": repeats,
        "estimated_raw_bytes": estimated_bytes,
        "by_model": dict(sorted(by_model.items())),
        "by_domain": dict(sorted(by_domain.items())),
        "by_language": dict(sorted(by_language.items())),
        "warnings": warnings,
        "conditions": conditions,
        "specs": specs,
    }


def campaign_progress(campaign: dict[str, Any], store: Any) -> dict[str, Any]:
    conditions: list[dict[str, Any]] = []
    completed_total = 0
    planned_total = 0
    for item in campaign.get("conditions", []):
        experiment_id = str(item["experiment_id"])
        planned = int(item.get("planned_runs", 0))
        completed = len(store.list_runs(experiment_id))
        planned_total += planned
        completed_total += completed
        row = dict(item)
        row["completed_runs"] = completed
        row["remaining_runs"] = max(0, planned - completed)
        conditions.append(row)
    return {
        "campaign_id": campaign.get("campaign_id"),
        "title": campaign.get("title"),
        "author": campaign.get("author") or "NicoMrx",
        "signature": campaign.get("signature") or "NicoMrx",
        "preregistration": campaign.get("preregistration", {"status": "draft"}),
        "condition_count": len(conditions),
        "planned_runs": planned_total,
        "completed_runs": completed_total,
        "remaining_runs": max(0, planned_total - completed_total),
        "progress": completed_total / planned_total if planned_total else 0,
        "conditions": conditions,
        "warnings": campaign.get("warnings", []),
    }
