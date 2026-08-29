from __future__ import annotations

import math
import re
from typing import Any


_LATIN_WORD = re.compile(r"^[A-Za-zÀ-ÖØ-öø-ÿ'’\-]+$")
_HAN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
_CYRILLIC = re.compile(r"[\u0400-\u04ff]")


def _topk_truncated_entropy(probs: list[float]) -> float:
    return -sum(value * math.log(value) for value in probs if value > 0)


def _script_code(token: str) -> int:
    value = token.strip()
    if _HAN.search(value):
        return 2
    if _CYRILLIC.search(value):
        return 3
    if value and _LATIN_WORD.fullmatch(value):
        return 1
    return 0


def to_cockpit_v1(artifact: dict[str, Any]) -> dict[str, Any]:
    """Compatibility view for the original Prismora cockpit.json contract."""
    result = artifact["result"]
    meta = result["meta"]
    lenses = list(meta.get("types") or meta.get("layers_by_type", {}).keys())
    layers_by_type = meta.get("layers_by_type", {})
    n_layers = {lens: len(layers_by_type.get(lens, [])) for lens in lenses}
    tokens: list[dict[str, Any]] = []

    for token in result["tokens"]:
        per_lens: dict[str, Any] = {}
        by_type = {item.get("type"): item for item in token.get("results", [])}
        for lens in lenses:
            item = by_type.get(lens)
            if not item:
                continue
            top_tokens = item.get("top_tokens", [])
            top_probs = item.get("top_probs", [])
            top1_prob: list[float] = []
            entropy: list[float] = []
            top1_lang: list[int] = []
            val_hit: list[int] = []
            for candidates, probs in zip(top_tokens, top_probs, strict=False):
                top1_prob.append(float(probs[0]) if probs else float("nan"))
                entropy.append(_topk_truncated_entropy([float(value) for value in probs]))
                top1_lang.append(_script_code(str(candidates[0])) if candidates else 0)
                val_hit.append(0)
            per_lens[lens] = {
                "layers": layers_by_type.get(lens, list(range(len(top_tokens)))),
                "top_tokens": top_tokens,
                "top_probs": top_probs,
                "m": {
                    "top1_prob": top1_prob,
                    "topk_truncated_entropy": entropy,
                    "top1_lang": top1_lang,
                    "val_hit": val_hit,
                },
            }
        tokens.append(
            {
                "kind": token.get("kind", "token"),
                "position": token["position"],
                "token": token["token"],
                "id": token["id"],
                "is_generated": token["is_generated"],
                "per_lens": per_lens,
            }
        )

    model = artifact["request"].get("model", {})
    return {
        "cockpit_schema_version": 1,
        "source": {
            "file": artifact["raw"]["relative_path"],
            "run_id": artifact["run_id"],
            "experiment_id": artifact["experiment_id"],
            "model_id": model.get("model_id"),
            "model_alias": model.get("alias"),
            "backend": artifact["request"].get("backend"),
            "request_sha256": artifact["provenance"].get("request_sha256"),
            "raw_sha256": artifact["provenance"].get("raw_sha256"),
        },
        "lenses": lenses,
        "n_layers": n_layers,
        "layers_by_type": layers_by_type,
        "is_mono_lens": len(lenses) == 1,
        "meta": meta,
        "done": result["done"],
        "tokens": tokens,
        "quality": artifact.get("quality", {}),
    }
