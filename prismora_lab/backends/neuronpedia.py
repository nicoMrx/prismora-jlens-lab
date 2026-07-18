from __future__ import annotations

import asyncio
from typing import Any

import httpx

from .base import BackendError, BackendResult, ExecutionBackend


class NeuronpediaBackend(ExecutionBackend):
    backend_id = "neuronpedia"

    def __init__(
        self,
        *,
        api_key: str | None,
        base_url: str = "https://www.neuronpedia.org",
        timeout_seconds: float = 300,
        max_retries: int = 3,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max(1, max_retries)
        self.transport = transport

    async def capabilities(self) -> dict[str, Any]:
        return {
            "schema": "prismora.backend-capabilities/v1",
            "backend_id": self.backend_id,
            "available": bool(self.api_key),
            "mock": False,
            "readouts": ["LOGIT_LENS", "JACOBIAN_LENS"],
            "interventions": ["steer", "swap", "ablate"],
            "forced_tokens": True,
            "fit_lens": False,
            "supports_chat": True,
            "supports_completion": True,
            "models": [],
            "limits": {"max_new_tokens": 256, "max_top_k": 8, "max_input_tokens": 4096, "max_batch_runs": None},
            "notes": [
                "Availability here means an API key is configured; model availability remains server-side.",
                "Both lens types can be requested in the same run.",
            ],
        }

    @staticmethod
    def build_payload(request: dict[str, Any]) -> dict[str, Any]:
        generation = request.get("generation", {})
        readout = request.get("readout", {})
        intervention = request.get("intervention") or {}
        top_k = int(readout.get("top_k", 8))
        max_new = int(generation.get("max_new_tokens", 128))
        if not 1 <= top_k <= 8:
            raise BackendError("Neuronpedia documents top_k in the range 1..8.")
        if not 0 <= max_new <= 256:
            raise BackendError("Neuronpedia documents max_new_tokens in the range 0..256.")

        payload: dict[str, Any] = {
            "modelId": request["model"]["model_id"],
            "type": readout.get("types", ["LOGIT_LENS", "JACOBIAN_LENS"]),
            "topN": top_k,
            "temperature": generation.get("temperature", 0),
            "numCompletionTokens": max_new,
            "prependBos": generation.get("prepend_bos", True),
            "enableThinking": generation.get("enable_thinking", False),
            "filterNonWordTokens": readout.get("filter_nonword_tokens", True),
            "stream": False,
        }

        input_ids = readout.get("input_token_ids")
        if input_ids:
            payload["inputTokenIds"] = input_ids
        elif "prompt" in request:
            payload["prompt"] = request["prompt"]
        elif "chat" in request:
            payload["chat"] = request["chat"]
        else:
            raise BackendError("Neuronpedia request needs prompt, chat, or input_token_ids.")

        cached_ids = readout.get("cached_token_ids")
        if cached_ids:
            payload["cachedTokenIds"] = cached_ids

        mode = intervention.get("mode", "none")
        if mode != "none":
            source_tokens = intervention.get("source_tokens") or []
            if not source_tokens:
                raise BackendError(f"Intervention mode {mode!r} requires source_tokens.")
            payload["steerTokens"] = [
                {"token": item["token"], "type": item["type"]} for item in source_tokens
            ]
            layers = intervention.get("layers") or []
            if layers:
                payload["steerLayers"] = layers
            payload["steerGeneratedTokens"] = intervention.get("apply_to_generated_tokens", False)
            if mode == "ablate":
                payload["steerAblate"] = True
            elif mode == "swap":
                target = intervention.get("target_token")
                if not target:
                    raise BackendError("Swap intervention requires target_token.")
                payload["swapToken"] = {"token": target["token"], "type": target["type"]}
                strength = intervention.get("strength")
                if strength is not None:
                    payload["steerStrength"] = strength
            elif mode == "steer":
                strength = intervention.get("strength")
                if strength is None:
                    raise BackendError("Steer intervention requires strength.")
                payload["steerStrength"] = strength
            else:
                raise BackendError(f"Unsupported intervention mode: {mode}")
        return payload

    async def run(self, request: dict[str, Any]) -> BackendResult:
        if not self.api_key:
            raise BackendError("NEURONPEDIA_API_KEY is not configured.", status_code=401)
        payload = self.build_payload(request)
        headers = {"x-api-key": self.api_key, "content-type": "application/json"}
        timeout = httpx.Timeout(self.timeout_seconds)
        last_error: Exception | None = None
        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            transport=self.transport,
            follow_redirects=True,
        ) as client:
            for attempt in range(self.max_retries):
                try:
                    response = await client.post("/api/lens/prompt", headers=headers, json=payload)
                except httpx.HTTPError as exc:
                    last_error = exc
                    if attempt + 1 >= self.max_retries:
                        break
                    await asyncio.sleep(2**attempt)
                    continue
                if response.status_code == 200:
                    try:
                        value = response.json()
                    except ValueError as exc:
                        raise BackendError("Neuronpedia returned invalid JSON.", status_code=502) from exc
                    if not all(key in value for key in ("meta", "tokens", "done")):
                        raise BackendError("Neuronpedia response is missing meta/tokens/done.", status_code=502, details=value)
                    return BackendResult(
                        value=value,
                        raw_bytes=response.content,
                        content_type=response.headers.get("content-type", "application/json"),
                    )
                body = response.text[:4000]
                if response.status_code == 429 or response.status_code >= 500:
                    last_error = BackendError(
                        f"Neuronpedia transient error {response.status_code}.",
                        status_code=response.status_code,
                        details=body,
                    )
                    if attempt + 1 < self.max_retries:
                        retry_after = response.headers.get("retry-after")
                        delay = float(retry_after) if retry_after and retry_after.replace(".", "", 1).isdigit() else float(2**attempt)
                        await asyncio.sleep(min(delay, 30))
                        continue
                raise BackendError(
                    f"Neuronpedia request failed with status {response.status_code}.",
                    status_code=response.status_code,
                    details=body,
                )
        raise BackendError(f"Neuronpedia request failed after retries: {last_error}", status_code=502)

    def raw_format(self) -> str:
        return "neuronpedia-buffered-json"
