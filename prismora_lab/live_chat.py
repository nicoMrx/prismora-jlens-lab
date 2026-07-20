from __future__ import annotations

import copy
import re
import uuid
from typing import Any

from fastapi import Body, HTTPException

from .matrix import expand_experiment
from .normalize import create_run_artifact
from .schema import validate
from .timeutil import utc_now_iso


_MODEL_CATALOG = [
    {"alias": "qwen3.6-27b", "model_id": "qwen3.6-27b", "label": "Qwen3.6-27B"},
    {"alias": "gpt-oss-20b", "model_id": "gpt-oss-20b", "label": "GPT-OSS-20B"},
    {"alias": "gemma-3-12b", "model_id": "gemma-3-12b", "label": "Gemma-3-12B"},
]
_MODEL_BY_ID = {item["model_id"]: item for item in _MODEL_CATALOG}
_SAFE = re.compile(r"[^a-z0-9._-]+")


def _model(value: str) -> dict[str, Any]:
    item = _MODEL_BY_ID.get(value)
    if item is None:
        raise ValueError(f"Unsupported live-chat model: {value}")
    return {
        "alias": item["alias"],
        "model_id": item["model_id"],
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
        "metadata": {"catalog_label": item["label"]},
    }


def _bounded_int(value: Any, *, default: int, minimum: int, maximum: int, label: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    if not minimum <= number <= maximum:
        raise ValueError(f"{label} must be in the range {minimum}..{maximum}.")
    return number


def _bounded_float(value: Any, *, default: float, minimum: float, maximum: float, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = default
    if not minimum <= number <= maximum:
        raise ValueError(f"{label} must be in the range {minimum}..{maximum}.")
    return number


def _live_spec(payload: dict[str, Any]) -> dict[str, Any]:
    message = str(payload.get("message") or "").strip()
    if not message:
        raise ValueError("Live chat needs a non-empty message.")
    if len(message) > 10_000:
        raise ValueError("Live-chat message exceeds 10,000 characters.")

    model = _model(str(payload.get("model_id") or "qwen3.6-27b"))
    temperature = _bounded_float(payload.get("temperature"), default=0, minimum=0, maximum=2, label="temperature")
    max_new_tokens = _bounded_int(
        payload.get("max_new_tokens"), default=128, minimum=1, maximum=256, label="max_new_tokens"
    )
    top_k = _bounded_int(payload.get("top_k"), default=8, minimum=1, maximum=8, label="top_k")
    requested_types = payload.get("lens_types") or ["JACOBIAN_LENS", "LOGIT_LENS"]
    lens_types = [value for value in requested_types if value in {"JACOBIAN_LENS", "LOGIT_LENS"}]
    lens_types = list(dict.fromkeys(lens_types))
    if not lens_types:
        raise ValueError("Live chat needs at least one supported J-Lens readout.")

    unique = uuid.uuid4().hex[:10]
    alias = _SAFE.sub("-", model["alias"].lower()).strip("-._")
    experiment_id = f"live-chat-{alias}-{unique}"[:80].rstrip("-._")
    spec = {
        "schema": "prismora.experiment/v2",
        "experiment_id": experiment_id,
        "title": f"Live chat · {model['metadata']['catalog_label']}",
        "description": "Single-turn live Neuronpedia observation created from Prismora Read.",
        "tags": ["live-chat", "neuronpedia", "nicomrx"],
        "hypothesis": {
            "primary": "Observe the returned J-Lens measurements without inferring intention, consciousness or hidden thought.",
            "falsifiers": ["The backend returns no valid token/layer readout for the requested response."],
            "exploratory": ["Inspect candidate trajectories and compare later runs only under explicit compatibility guards."],
        },
        "preregistration": {"status": "draft", "locked_at": None, "spec_sha256": None, "amendments": []},
        "models": [model],
        "prompts": [{"prompt_id": "message", "chat": [{"role": "user", "content": message}], "metadata": {}}],
        "matrix": {"factors": {}, "bindings": {}, "repeats": 1},
        "generation": {
            "temperature": temperature,
            "max_new_tokens": max_new_tokens,
            "seed": None,
            "prepend_bos": True,
            "enable_thinking": bool(payload.get("enable_thinking", False)),
            "frequency_penalty": 0,
        },
        "readout": {
            "types": lens_types,
            "top_k": top_k,
            "filter_nonword_tokens": bool(payload.get("filter_nonword_tokens", True)),
            "exclude_first_n_positions": 0,
        },
        "intervention": None,
        "analysis": {
            "primary_metric": "descriptive J-Lens trajectory",
            "secondary_metrics": ["top-1 transitions", "candidate probability by measured layer"],
            "exclusions": ["Technical channel markers must be separated from visible final-answer positions when present."],
            "compare_absolute_and_relative_depth": True,
            "semantic_families": {},
            "generated_positions_only": False,
            "presence_min_probability": 0.01,
            "notes": "Live single-turn observation signed by NicoMrx. A readout is not a causal or cognitive claim.",
        },
        "stopping_rule": "Complete this single live observation unless the backend, quota or safety layer rejects it.",
        "metadata": {
            "author": "NicoMrx",
            "signature": "NicoMrx",
            "source": "prismora-v4-live-chat",
            "created_at": utc_now_iso(),
        },
    }
    validate("experiment", spec)
    return spec


def mount_live_chat_routes(app: Any, context: Any) -> None:
    if getattr(app.state, "prismora_live_chat_mounted", False):
        return

    @app.get("/api/live/models")
    async def live_models() -> dict[str, Any]:
        return {
            "models": copy.deepcopy(_MODEL_CATALOG),
            "defaults": {
                "model_id": "qwen3.6-27b",
                "temperature": 0,
                "max_new_tokens": 128,
                "top_k": 8,
                "lens_types": ["JACOBIAN_LENS", "LOGIT_LENS"],
            },
            "signature": "NicoMrx",
        }

    @app.post("/api/live/chat")
    async def live_chat(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        if not context.session.neuronpedia_api_key or not context.session.neuronpedia_connected:
            raise HTTPException(
                status_code=409,
                detail="Neuronpedia must be configured and successfully tested before a live chat run.",
            )
        try:
            spec = _live_spec(payload)
            context.store.save_experiment(spec)
            planned = expand_experiment(spec)[0]
            backend = context.backends.get("neuronpedia")
            if backend is None:
                raise ValueError("Neuronpedia backend is unavailable.")
            backend_result = await backend.run(copy.deepcopy(planned.request))
            if len(backend_result.raw_bytes) > context.settings.max_raw_bytes:
                raise ValueError(
                    f"Raw result is {len(backend_result.raw_bytes)} bytes, above "
                    f"PRISMORA_MAX_RAW_BYTES={context.settings.max_raw_bytes}."
                )
            artifact = create_run_artifact(
                store=context.store,
                experiment_id=planned.experiment_id,
                run_id=planned.run_id,
                request=planned.request,
                raw=backend_result.value,
                raw_format=backend.raw_format(),
                raw_bytes=backend_result.raw_bytes,
                raw_content_type=backend_result.content_type,
                backend_environment={
                    "mode": "live-chat",
                    "author": "NicoMrx",
                    "signature": "NicoMrx",
                    "session_locale": context.session.locale,
                },
            )
            artifact.setdefault("derived", {})["live_chat"] = {
                "single_turn": True,
                "signed_by": "NicoMrx",
                "visible_final_normalization_required": bool(
                    artifact.get("result", {}).get("meta", {}).get("channels", {}).get("analysis", {}).get("present")
                ),
            }
            context.store.save_run(artifact)
            return artifact
        except HTTPException:
            raise
        except Exception as exc:
            status = getattr(exc, "status_code", None) or 502
            raise HTTPException(
                status_code=int(status),
                detail={"message": str(exc), "type": type(exc).__name__},
            ) from exc

    app.state.prismora_live_chat_mounted = True
