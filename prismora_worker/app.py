from __future__ import annotations

import argparse
import asyncio
import os
from typing import Any

from fastapi import Body, FastAPI, Header, HTTPException

from .runtime import load_runtime


TOKEN = os.getenv("PRISMORA_WORKER_TOKEN", "").strip() or None
RUNTIME = load_runtime()
RUN_LOCK = asyncio.Lock()

app = FastAPI(
    title="Prismora GPU Worker Contract",
    version="0.2.1",
    description="Vendor-neutral worker API for mock or pinned open-weight J-Lens runtimes.",
)


def _authorize(authorization: str | None) -> None:
    if TOKEN and authorization != f"Bearer {TOKEN}":
        raise HTTPException(status_code=401, detail="Invalid worker token")


@app.get("/v1/health")
async def health(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _authorize(authorization)
    return {"ok": True, "runtime_id": RUNTIME.runtime_id, "mock": bool(getattr(RUNTIME, "is_mock", False))}


@app.get("/v1/capabilities")
async def capabilities(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _authorize(authorization)
    return await RUNTIME.capabilities()


@app.post("/v1/run")
async def run(payload: dict[str, Any] = Body(...), authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _authorize(authorization)
    request = payload.get("request")
    if not isinstance(request, dict):
        raise HTTPException(status_code=422, detail="Body must contain request object")
    try:
        # Runtime implementations own shared model weights, hooks and random
        # number generators. The public max_batch_runs=1 contract is enforced
        # here for every plugin, not merely advertised in capabilities.
        async with RUN_LOCK:
            raw = await RUNTIME.run(request)
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not isinstance(raw, dict) or not all(key in raw for key in ("meta", "tokens", "done")):
        raise HTTPException(status_code=502, detail="Runtime must return meta/tokens/done")
    # Return the raw meta/tokens/done object directly so the control plane can
    # archive the exact HTTP response bytes without stripping an envelope.
    return raw


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Prismora worker contract service.")
    parser.add_argument("--host", default=os.getenv("PRISMORA_WORKER_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("PRISMORA_WORKER_PORT", "8100")))
    args = parser.parse_args()
    import uvicorn

    uvicorn.run("prismora_worker.app:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
