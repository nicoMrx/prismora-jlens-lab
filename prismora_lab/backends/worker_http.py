from __future__ import annotations

from typing import Any

import httpx

from .base import BackendError, BackendResult, ExecutionBackend


class WorkerHTTPBackend(ExecutionBackend):
    backend_id = "worker"

    def __init__(
        self,
        *,
        base_url: str | None,
        token: str | None = None,
        timeout_seconds: float = 600,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/") if base_url else None
        self.token = token
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    def _headers(self) -> dict[str, str]:
        headers = {"content-type": "application/json"}
        if self.token:
            headers["authorization"] = f"Bearer {self.token}"
        return headers

    async def capabilities(self) -> dict[str, Any]:
        if not self.base_url:
            return {
                "schema": "prismora.backend-capabilities/v1",
                "backend_id": self.backend_id,
                "available": False,
                "mock": False,
                "readouts": [],
                "interventions": [],
                "forced_tokens": False,
                "fit_lens": False,
                "supports_chat": True,
                "supports_completion": True,
                "models": [],
                "limits": {"max_new_tokens": 0, "max_top_k": 1, "max_input_tokens": None, "max_batch_runs": None},
                "notes": ["PRISMORA_WORKER_URL is not configured."],
            }
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(5),
                transport=self.transport,
            ) as client:
                response = await client.get("/v1/capabilities", headers=self._headers())
                response.raise_for_status()
                value = response.json()
                value["available"] = True
                return value
        except (httpx.HTTPError, ValueError) as exc:
            return {
                "schema": "prismora.backend-capabilities/v1",
                "backend_id": self.backend_id,
                "available": False,
                "mock": False,
                "readouts": ["LOGIT_LENS", "JACOBIAN_LENS"],
                "interventions": ["steer", "swap", "ablate"],
                "forced_tokens": True,
                "fit_lens": True,
                "supports_chat": True,
                "supports_completion": True,
                "models": [],
                "limits": {"max_new_tokens": 4096, "max_top_k": 64, "max_input_tokens": None, "max_batch_runs": 1},
                "notes": [f"Worker is configured but unreachable: {type(exc).__name__}: {exc}"],
            }

    async def run(self, request: dict[str, Any]) -> BackendResult:
        if not self.base_url:
            raise BackendError("PRISMORA_WORKER_URL is not configured.", status_code=503)
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.timeout_seconds),
                transport=self.transport,
            ) as client:
                response = await client.post("/v1/run", headers=self._headers(), json={"request": request})
        except httpx.HTTPError as exc:
            raise BackendError(f"GPU worker request failed: {exc}", status_code=502) from exc
        if response.status_code != 200:
            raise BackendError(
                f"GPU worker returned {response.status_code}.",
                status_code=response.status_code,
                details=response.text[:4000],
            )
        try:
            value = response.json()
        except ValueError as exc:
            raise BackendError("GPU worker returned invalid JSON.", status_code=502) from exc
        raw = value.get("result", value)
        if not all(key in raw for key in ("meta", "tokens", "done")):
            raise BackendError("GPU worker response is missing meta/tokens/done.", status_code=502)
        if "result" in value:
            # Compatibility with pre-v0.2 wrappers. The exact envelope remains
            # the HTTP evidence, while result contains the normalized payload.
            content_type = response.headers.get("content-type", "application/json") + "; envelope=legacy"
        else:
            content_type = response.headers.get("content-type", "application/json")
        return BackendResult(value=raw, raw_bytes=response.content, content_type=content_type)

    def raw_format(self) -> str:
        return "prismora-worker-json"
