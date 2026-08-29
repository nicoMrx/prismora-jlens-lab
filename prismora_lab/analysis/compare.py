from __future__ import annotations

from collections import defaultdict
from typing import Any


def _result_for_lens(token: dict[str, Any], lens: str) -> dict[str, Any] | None:
    for result in token.get("results", []):
        if result.get("type") == lens:
            return result
    return None




def _top_tie_set(candidates: list[Any], probs: list[Any], *, epsilon: float = 1e-12) -> set[str]:
    if not candidates:
        return set()
    if not probs:
        return {str(candidates[0])}
    values = [float(v) for v in probs[:len(candidates)]]
    if not values:
        return {str(candidates[0])}
    maximum = max(values)
    return {str(candidates[i]) for i, value in enumerate(values) if abs(value - maximum) <= epsilon}

def _top1_agrees(ca: list[Any], pa: list[Any], cb: list[Any], pb: list[Any]) -> bool:
    return bool(_top_tie_set(ca, pa) & _top_tie_set(cb, pb))

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
            probs_a = result_a.get("top_probs", [])[map_a[layer]] if result_a.get("top_probs") else []
            probs_b = result_b.get("top_probs", [])[map_b[layer]] if result_b.get("top_probs") else []
            if not candidates_a or not candidates_b:
                continue
            compared += 1
            agreements += int(_top1_agrees(candidates_a, probs_a, candidates_b, probs_b))
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
    probability_shape_mismatches = 0
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
            top1_equal += int(_top1_agrees(candidates_a, probs_a, candidates_b, probs_b))
            topk_equal += int(candidates_a == candidates_b)
            if not isinstance(probs_a, list) or not isinstance(probs_b, list) or len(probs_a) != len(probs_b):
                probability_shape_mismatches += 1
                continue
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
        and probability_shape_mismatches == 0
    )
    warnings: list[str] = []
    if not token_ids_identical:
        warnings.append("Surface token-ID sequences differ; numerical read-out equivalence is not established.")
    if not layers_identical:
        warnings.append("Actual layer lists differ; only shared layers were compared.")
    if missing_cells:
        warnings.append(f"{missing_cells} aligned layer-position cells were missing or malformed.")
    if probability_shape_mismatches:
        warnings.append(
            f"{probability_shape_mismatches} aligned cells had different probability-vector lengths."
        )
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
        "probability_shape_mismatches": probability_shape_mismatches,
        "top1_agreement": top1_rate,
        "exact_topk_rate": topk_rate,
        "probability_values_compared": total_prob,
        "probability_within_tolerance_rate": probability_rate,
        "max_probability_abs_delta": global_max_delta if total_prob else None,
        "equivalent_under_declared_tolerance": equivalent,
        "layers": rows,
        "warnings": warnings,
    }


def strict_comparison_facts(
    a: dict[str, Any],
    b: dict[str, Any],
    lens: str,
    *,
    scope: str = "prompt_fixed",
    probability_abs_tolerance: float = 0.0,
) -> dict[str, Any]:
    """Deterministic readout facts for Understand and API consumers."""
    if probability_abs_tolerance < 0:
        raise ValueError("probability_abs_tolerance must be non-negative")
    if scope not in {"prompt_fixed", "generated_ordinal"}:
        raise ValueError("scope must be prompt_fixed or generated_ordinal")
    tokens_a = a["result"]["tokens"]
    tokens_b = b["result"]["tokens"]
    if scope == "prompt_fixed":
        seq_a = [t for t in tokens_a if not t.get("is_generated")]
        by_pos_b = {t.get("position"): t for t in tokens_b if not t.get("is_generated")}
        pairs = [(ta, by_pos_b.get(ta.get("position"))) for ta in seq_a]
    else:
        ga = [t for t in tokens_a if t.get("is_generated")]
        gb = [t for t in tokens_b if t.get("is_generated")]
        pairs = list(zip(ga, gb, strict=False))
    layers_a = list(a["result"].get("meta", {}).get("layers_by_type", {}).get(lens, []))
    layers_b = list(b["result"].get("meta", {}).get("layers_by_type", {}).get(lens, []))
    ia = {layer: idx for idx, layer in enumerate(layers_a)}
    ib = {layer: idx for idx, layer in enumerate(layers_b)}
    shared = sorted(set(ia) & set(ib))
    warnings: list[str] = []
    if scope == "generated_ordinal":
        warnings.append("Generated tokens are aligned by ordinal position only; no semantic alignment is attempted.")
    first_strict = None
    first_top1 = None
    rows = []
    missing = []
    for layer in shared:
        cells = strict_div = top1_div = 0
        for ordinal, (ta, tb) in enumerate(pairs):
            if tb is None or (scope == "prompt_fixed" and ta.get("id") != tb.get("id")):
                missing.append({"layer": layer, "position": ta.get("position"), "reason": "missing_or_token_id_mismatch"})
                continue
            ra = _result_for_lens(ta, lens); rb = _result_for_lens(tb, lens)
            try:
                ca = ra["top_tokens"][ia[layer]]; cb = rb["top_tokens"][ib[layer]]  # type: ignore[index]
                pa = ra.get("top_probs", [])[ia[layer]]; pb = rb.get("top_probs", [])[ib[layer]]  # type: ignore[union-attr]
            except Exception:
                missing.append({"layer": layer, "position": ta.get("position", ordinal), "reason": "missing_or_malformed_cell"})
                continue
            if not ca or not cb:
                missing.append({"layer": layer, "position": ta.get("position", ordinal), "reason": "empty_topk"})
                continue
            cells += 1
            top1_changed = not _top1_agrees(ca, pa, cb, pb)
            prob_changed = any(abs(float(x)-float(y)) > probability_abs_tolerance for x,y in zip(pa, pb, strict=False)) or len(pa) != len(pb)
            strict_changed = top1_changed or ca != cb or prob_changed
            top1_div += int(top1_changed); strict_div += int(strict_changed)
            cell = {"layer": layer, "position": ta.get("position", ordinal), "token_id": ta.get("id")}
            if strict_changed and first_strict is None: first_strict = cell
            if top1_changed and first_top1 is None: first_top1 = cell
        rows.append({"layer": layer, "cells": cells, "strict_divergence_rate": strict_div/cells if cells else None, "top1_divergence_rate": top1_div/cells if cells else None})
    if missing:
        warnings.append(f"{len(missing)} aligned layer-position cells were missing or malformed.")
    ga = [t.get("id") for t in tokens_a if t.get("is_generated")]
    gb = [t.get("id") for t in tokens_b if t.get("is_generated")]
    return {"schema":"prismora.compare_facts/v1","run_a":a["run_id"],"run_b":b["run_id"],"lens":lens,"scope":scope,"probability_abs_tolerance":probability_abs_tolerance,"generated_token_ids_identical":ga==gb,"generated_text_a":a["result"].get("done",{}).get("completion"),"generated_text_b":b["result"].get("done",{}).get("completion"),"shared_layers":shared,"first_strict_divergence":first_strict,"first_top1_divergence":first_top1,"per_layer":rows,"missing_cells":missing,"warnings":warnings}
