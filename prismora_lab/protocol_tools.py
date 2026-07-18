from __future__ import annotations

import copy
from typing import Any


def make_filter_replay_spec(
    artifact: dict[str, Any],
    *,
    experiment_id: str,
    title: str | None = None,
) -> dict[str, Any]:
    """Create an exact-token replay protocol for filter calibration.

    The generated tokens from the source run are fed back as input_token_ids;
    therefore both filter conditions observe the same pre-tokenized sequence.
    """
    request = artifact["request"]
    token_ids = [int(token["id"]) for token in artifact["result"]["tokens"]]
    model = copy.deepcopy(request["model"])
    model["backend"] = request["backend"]
    prompt_entry: dict[str, Any] = {"prompt_id": f"replay_{request['prompt_id']}"}
    if "prompt" in request:
        prompt_entry["prompt"] = request["prompt"]
    else:
        prompt_entry["chat"] = copy.deepcopy(request.get("chat", [{"role": "user", "content": "Forced token replay"}]))
    readout = copy.deepcopy(request["readout"])
    readout["input_token_ids"] = token_ids
    readout.pop("cached_token_ids", None)
    return {
        "schema": "prismora.experiment/v2",
        "experiment_id": experiment_id,
        "title": title or f"Exact-token filter replay from {artifact['run_id']}",
        "description": "Replays one exact pre-tokenized sequence under filter_nonword_tokens=false/true. No generation occurs.",
        "tags": ["calibration", "filter-nonword", "forced-replay"],
        "hypothesis": {
            "primary": "Changing only the read-out filter changes observable rankings while the token-id sequence remains fixed.",
            "falsifiers": [
                "The two conditions produce different input token-id sequences.",
                "The top-k read-outs are identical within the predefined tolerance at every compared cell."
            ],
            "exploratory": ["Measure whether the effect is concentrated in early layers."],
        },
        "preregistration": {"status": "draft", "locked_at": None, "spec_sha256": None, "amendments": []},
        "models": [model],
        "prompts": [prompt_entry],
        "matrix": {
            "factors": {"filter_nonword": [False, True]},
            "bindings": {"filter_nonword": "readout.filter_nonword_tokens"},
            "repeats": 1,
        },
        "generation": {
            "temperature": request.get("generation", {}).get("temperature", 0),
            "max_new_tokens": 0,
            "seed": request.get("generation", {}).get("seed"),
            "prepend_bos": request.get("generation", {}).get("prepend_bos", True),
            "enable_thinking": request.get("generation", {}).get("enable_thinking", False),
            "frequency_penalty": request.get("generation", {}).get("frequency_penalty", 0),
        },
        "readout": readout,
        "intervention": None,
        "analysis": {
            "primary_metric": "top1_change_rate",
            "secondary_metrics": ["mean_topk_jaccard", "rank_displacement", "effect_by_layer"],
            "exclusions": ["Cells missing from either condition"],
            "compare_absolute_and_relative_depth": True,
            "generated_positions_only": False,
            "presence_min_probability": 0.01,
            "notes": "Use comparison mode filter_effect. The source run is provenance, not an independent replicate of this replay.",
        },
        "stopping_rule": "Complete both exact-token filter conditions once.",
        "metadata": {"source_run_id": artifact["run_id"], "source_result_sha256": artifact["provenance"]["canonical_result_sha256"]},
    }
