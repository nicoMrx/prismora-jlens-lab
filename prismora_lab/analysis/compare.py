from __future__ import annotations

from collections import defaultdict
from typing import Any


def _result_for_lens(token: dict[str, Any], lens: str) -> dict[str, Any] | None:
    for result in token.get("results", []):
        if result.get("type") == lens:
            return result
    return None


def _generated_tokens(artifact: dict[str, Any]) -> list[dict[str, Any]]:
    return [token for token in artifact["result"]["tokens"] if token.get("is_generated")]


def top1_agreement_by_layer(a: dict[str, Any], b: dict[str, Any], lens: str) -> dict[str, Any]:
    meta_a = a["result"]["meta"]
    meta_b = b["result"]["meta"]
    layers_a = meta_a.get("layers_by_type", {}).get(lens, [])
    layers_b = meta_b.get("layers_by_type", {}).get(lens, [])
    map_a = {layer: index for index, layer in enumerate(layers_a)}
    map_b = {layer: index for index, layer in enumerate(layers_b)}
    shared_layers = sorted(set(map_a) & set(map_b))
    tokens_a = _generated_tokens(a)
    tokens_b = _generated_tokens(b)
    pair_count = min(len(tokens_a), len(tokens_b))
    rows: list[dict[str, Any]] = []

    for layer in shared_layers:
        compared = 0
        agreements = 0
        jaccards: list[float] = []
        for token_a, token_b in zip(tokens_a[:pair_count], tokens_b[:pair_count], strict=False):
            result_a = _result_for_lens(token_a, lens)
            result_b = _result_for_lens(token_b, lens)
            if not result_a or not result_b:
                continue
            candidates_a = result_a.get("top_tokens", [])[map_a[layer]]
            candidates_b = result_b.get("top_tokens", [])[map_b[layer]]
            if not candidates_a or not candidates_b:
                continue
            compared += 1
            agreements += int(candidates_a[0] == candidates_b[0])
            set_a, set_b = set(candidates_a), set(candidates_b)
            union = set_a | set_b
            jaccards.append(len(set_a & set_b) / len(union) if union else 1.0)
        rows.append(
            {
                "layer": layer,
                "relative_depth_a": layer / max(layers_a) if layers_a and max(layers_a) else 0,
                "relative_depth_b": layer / max(layers_b) if layers_b and max(layers_b) else 0,
                "positions_compared": compared,
                "top1_agreement": agreements / compared if compared else None,
                "mean_topk_jaccard": sum(jaccards) / len(jaccards) if jaccards else None,
            }
        )
    valid = [row["top1_agreement"] for row in rows if row["top1_agreement"] is not None]
    return {
        "lens": lens,
        "run_a": a["run_id"],
        "run_b": b["run_id"],
        "generated_positions_a": len(tokens_a),
        "generated_positions_b": len(tokens_b),
        "aligned_positions": pair_count,
        "mean_top1_agreement": sum(valid) / len(valid) if valid else None,
        "layers": rows,
        "warnings": [
            "Positions are aligned by generated-token ordinal, not semantic token alignment."
        ] if len(tokens_a) != len(tokens_b) else [],
    }


def readout_filter_effect(a: dict[str, Any], b: dict[str, Any], lens: str) -> dict[str, Any]:
    """Quantify rank/readout changes for exact token-id replays under two filters."""
    tokens_a = a["result"]["tokens"]
    tokens_b = b["result"]["tokens"]
    by_position_b = {token["position"]: token for token in tokens_b}
    layers_a = a["result"]["meta"].get("layers_by_type", {}).get(lens, [])
    layers_b = b["result"]["meta"].get("layers_by_type", {}).get(lens, [])
    map_b = {layer: index for index, layer in enumerate(layers_b)}
    per_layer: dict[int, dict[str, float]] = defaultdict(lambda: {"cells": 0, "changed_top1": 0, "jaccard_sum": 0.0})
    for token_a in tokens_a:
        token_b = by_position_b.get(token_a["position"])
        if not token_b or token_a.get("id") != token_b.get("id"):
            continue
        result_a = _result_for_lens(token_a, lens)
        result_b = _result_for_lens(token_b, lens)
        if not result_a or not result_b:
            continue
        for index_a, layer in enumerate(layers_a):
            index_b = map_b.get(layer)
            if index_b is None:
                continue
            candidates_a = result_a["top_tokens"][index_a]
            candidates_b = result_b["top_tokens"][index_b]
            if not candidates_a or not candidates_b:
                continue
            row = per_layer[layer]
            row["cells"] += 1
            row["changed_top1"] += int(candidates_a[0] != candidates_b[0])
            union = set(candidates_a) | set(candidates_b)
            row["jaccard_sum"] += len(set(candidates_a) & set(candidates_b)) / len(union) if union else 1.0
    rows = []
    for layer in sorted(per_layer):
        row = per_layer[layer]
        cells = int(row["cells"])
        rows.append(
            {
                "layer": layer,
                "cells": cells,
                "top1_change_rate": row["changed_top1"] / cells if cells else None,
                "mean_topk_jaccard": row["jaccard_sum"] / cells if cells else None,
            }
        )
    total_cells = sum(row["cells"] for row in rows)
    total_changes = sum((row["top1_change_rate"] or 0) * row["cells"] for row in rows)
    return {
        "lens": lens,
        "run_a": a["run_id"],
        "run_b": b["run_id"],
        "surface_token_ids_identical": [token.get("id") for token in tokens_a] == [token.get("id") for token in tokens_b],
        "cells_compared": total_cells,
        "top1_change_rate": total_changes / total_cells if total_cells else None,
        "layers": rows,
    }



def bridge_equivalence(
    a: dict[str, Any],
    b: dict[str, Any],
    lens: str,
    *,
    probability_abs_tolerance: float = 0.01,
) -> dict[str, Any]:
    """Strict public/private bridge comparison over every aligned position.

    The bridge is intentionally token/rank based because public J-Lens exports
    expose decoded candidate strings and probabilities, not candidate token IDs.
    Exact surface token IDs, actual layer numbers and ranked candidate strings
    must agree before probability tolerance can be interpreted as numerical
    equivalence.
    """
    if probability_abs_tolerance < 0:
        raise ValueError("probability_abs_tolerance must be non-negative")
    tokens_a = a["result"]["tokens"]
    tokens_b = b["result"]["tokens"]
    ids_a = [token.get("id") for token in tokens_a]
    ids_b = [token.get("id") for token in tokens_b]
    meta_a = a["result"].get("meta", {})
    meta_b = b["result"].get("meta", {})
    layers_a = list(meta_a.get("layers_by_type", {}).get(lens, []))
    layers_b = list(meta_b.get("layers_by_type", {}).get(lens, []))
    index_a = {layer: index for index, layer in enumerate(layers_a)}
    index_b = {layer: index for index, layer in enumerate(layers_b)}
    shared_layers = sorted(set(index_a) & set(index_b))
    by_position_b = {int(token["position"]): token for token in tokens_b}

    rows: list[dict[str, Any]] = []
    total_cells = total_top1 = total_topk = total_prob = total_prob_within = 0
    global_max_delta = 0.0
    missing_cells = 0
    for layer in shared_layers:
        cells = top1_equal = topk_equal = prob_values = prob_within = 0
        max_delta = 0.0
        for token_a in tokens_a:
            token_b = by_position_b.get(int(token_a["position"]))
            if token_b is None or token_a.get("id") != token_b.get("id"):
                continue
            result_a = _result_for_lens(token_a, lens)
            result_b = _result_for_lens(token_b, lens)
            if not result_a or not result_b:
                missing_cells += 1
                continue
            try:
                candidates_a = result_a["top_tokens"][index_a[layer]]
                candidates_b = result_b["top_tokens"][index_b[layer]]
                probs_a = result_a["top_probs"][index_a[layer]]
                probs_b = result_b["top_probs"][index_b[layer]]
            except (IndexError, KeyError, TypeError):
                missing_cells += 1
                continue
            if not candidates_a or not candidates_b:
                missing_cells += 1
                continue
            cells += 1
            top1_equal += int(candidates_a[0] == candidates_b[0])
            topk_equal += int(candidates_a == candidates_b)
            for pa, pb in zip(probs_a, probs_b, strict=False):
                delta = abs(float(pa) - float(pb))
                prob_values += 1
                prob_within += int(delta <= probability_abs_tolerance)
                max_delta = max(max_delta, delta)
        total_cells += cells
        total_top1 += top1_equal
        total_topk += topk_equal
        total_prob += prob_values
        total_prob_within += prob_within
        global_max_delta = max(global_max_delta, max_delta)
        rows.append(
            {
                "layer": layer,
                "cells": cells,
                "top1_agreement": top1_equal / cells if cells else None,
                "exact_topk_rate": topk_equal / cells if cells else None,
                "probability_values_compared": prob_values,
                "probability_within_tolerance_rate": prob_within / prob_values if prob_values else None,
                "max_probability_abs_delta": max_delta if prob_values else None,
            }
        )

    token_ids_identical = ids_a == ids_b
    layers_identical = layers_a == layers_b
    top1_rate = total_top1 / total_cells if total_cells else None
    topk_rate = total_topk / total_cells if total_cells else None
    probability_rate = total_prob_within / total_prob if total_prob else None
    equivalent = bool(
        token_ids_identical
        and layers_identical
        and total_cells > 0
        and top1_rate == 1.0
        and topk_rate == 1.0
        and probability_rate == 1.0
        and missing_cells == 0
    )
    warnings: list[str] = []
    if not token_ids_identical:
        warnings.append("Surface token-ID sequences differ; numerical read-out equivalence is not established.")
    if not layers_identical:
        warnings.append("Actual layer lists differ; only shared layers were compared.")
    if missing_cells:
        warnings.append(f"{missing_cells} aligned layer-position cells were missing or malformed.")
    warnings.append(
        "Candidate read-out IDs are unavailable in the public export contract; exact top-k comparison uses decoded token strings."
    )
    return {
        "mode": "bridge",
        "lens": lens,
        "run_a": a["run_id"],
        "run_b": b["run_id"],
        "probability_abs_tolerance": probability_abs_tolerance,
        "surface_token_ids_identical": token_ids_identical,
        "actual_layer_lists_identical": layers_identical,
        "positions_a": len(tokens_a),
        "positions_b": len(tokens_b),
        "shared_layers": shared_layers,
        "cells_compared": total_cells,
        "missing_cells": missing_cells,
        "top1_agreement": top1_rate,
        "exact_topk_rate": topk_rate,
        "probability_values_compared": total_prob,
        "probability_within_tolerance_rate": probability_rate,
        "max_probability_abs_delta": global_max_delta if total_prob else None,
        "equivalent_under_declared_tolerance": equivalent,
        "layers": rows,
        "warnings": warnings,
    }
