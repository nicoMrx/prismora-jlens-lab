from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from ..canonical import sha256_json
from ..timeutil import utc_now_iso


def build_top1_reference_distribution(
    artifacts: list[dict[str, Any]],
    *,
    lens: str,
    position_scope: str = "all",
    max_tokens_per_layer: int = 30,
) -> dict[str, Any]:
    """Empirical prompt-insensitive reference distribution by actual layer.

    This is a frequency baseline, not evidence that frequent early tokens are
    training fossils. Model, lens, filter, template and position scope remain
    explicit provenance dimensions.
    """
    if position_scope not in {"all", "context", "generated"}:
        raise ValueError("position_scope must be all, context, or generated")
    counts: dict[int, Counter[str]] = defaultdict(Counter)
    cells: Counter[int] = Counter()
    layers_seen: set[int] = set()
    filter_values: set[bool] = set()
    model_ids: set[str] = set()
    lens_ids: set[str] = set()

    for artifact in artifacts:
        request = artifact["request"]
        model_ids.add(str(request.get("model", {}).get("model_id")))
        lens_ids.add(str(request.get("model", {}).get("lens_id")))
        filter_values.add(bool(request.get("readout", {}).get("filter_nonword_tokens", True)))
        meta = artifact["result"]["meta"]
        layers = meta.get("layers_by_type", {}).get(lens, [])
        for token in artifact["result"]["tokens"]:
            if position_scope == "generated" and not token.get("is_generated"):
                continue
            if position_scope == "context" and token.get("is_generated"):
                continue
            result = next((item for item in token.get("results", []) if item.get("type") == lens), None)
            if not result:
                continue
            for index, layer in enumerate(layers):
                candidates = result.get("top_tokens", [])[index]
                if not candidates:
                    continue
                layer = int(layer)
                layers_seen.add(layer)
                cells[layer] += 1
                counts[layer][str(candidates[0])] += 1

    per_layer: list[dict[str, Any]] = []
    for layer in sorted(layers_seen):
        denominator = cells[layer]
        top = [
            {"token": token, "count": count, "frequency": count / denominator if denominator else 0}
            for token, count in counts[layer].most_common(max_tokens_per_layer)
        ]
        diversity = len(counts[layer]) / denominator if denominator else 0
        per_layer.append(
            {
                "layer": layer,
                "cells": denominator,
                "distinct_top1_tokens": len(counts[layer]),
                "top1_diversity_ratio": diversity,
                "top_tokens": top,
            }
        )

    run_ids = [artifact["run_id"] for artifact in artifacts]
    source_hashes = [artifact["provenance"]["canonical_result_sha256"] for artifact in artifacts]
    identity = {
        "run_ids": run_ids,
        "source_hashes": source_hashes,
        "lens": lens,
        "position_scope": position_scope,
        "filter_values": sorted(filter_values),
    }
    return {
        "schema": "prismora.baseline/top1-reference-v1",
        "baseline_id": f"baseline-{sha256_json(identity)[:16]}",
        "created_at": utc_now_iso(),
        "lens": lens,
        "position_scope": position_scope,
        "run_ids": run_ids,
        "source_result_sha256": source_hashes,
        "model_ids": sorted(model_ids),
        "lens_ids": sorted(lens_ids),
        "filter_nonword_values": sorted(filter_values),
        "mixed_filter_warning": len(filter_values) > 1,
        "per_layer": per_layer,
        "interpretation_limit": "A frequent token is part of an empirical readout background. Its mechanistic origin is not inferred by this baseline.",
    }
