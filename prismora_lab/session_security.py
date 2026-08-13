from __future__ import annotations

from typing import Any, Awaitable, Callable

import httpx
from fastapi import Request
from fastapi.responses import JSONResponse, Response

from .backends.neuronpedia import NeuronpediaBackend
from .backends.worker_http import WorkerHTTPBackend


CallNext = Callable[[Request], Awaitable[Response]]


def _public_settings(context: Any) -> dict[str, Any]:
    """Return session settings without ever exposing the API key."""
    return {
        "display_name": context.session.display_name,
        "locale": context.session.locale,
        "theme": context.session.theme,
        "worker_url": context.session.worker_url,
        "neuronpedia_key_configured": bool(context.session.neuronpedia_api_key),
        "neuronpedia_connected": bool(context.session.neuronpedia_connected),
        "backends": sorted(context.backends),
        "models": [],
    }


def _replace_neuronpedia_backend(context: Any, api_key: str | None) -> None:
    if "neuronpedia" not in context.backends:
        return
    context.backends["neuronpedia"] = NeuronpediaBackend(
        api_key=api_key,
        base_url=context.settings.neuronpedia_base_url,
        timeout_seconds=context.settings.neuronpedia_timeout_seconds,
        max_retries=context.settings.neuronpedia_max_retries,
    )


def _replace_worker_backend(context: Any, worker_url: str | None) -> None:
    if "worker" not in context.backends:
        return
    context.backends["worker"] = WorkerHTTPBackend(
        base_url=worker_url,
        token=context.settings.worker_token,
    )


def _localized(context: Any, *, fr: str, en: str) -> str:
    return fr if context.session.locale == "fr" else en


def install_session_security(app: Any, context: Any) -> None:
    """Install authoritative session routes ahead of the legacy handlers.

    The original v0.2 handlers treated any saved key as connected and accepted
    every upstream status below 500. This middleware preserves the public API
    while enforcing stricter semantics without persisting secrets.
    """
    if getattr(app.state, "prismora_session_security_installed", False):
        return

    if context.session.neuronpedia_api_key is None and context.settings.neuronpedia_api_key:
        context.session.neuronpedia_api_key = context.settings.neuronpedia_api_key
        context.session.neuronpedia_connected = False

    @app.middleware("http")
    async def secure_session_routes(request: Request, call_next: CallNext) -> Response:
        path = request.url.path
        method = request.method.upper()

        if path == "/api/session/settings" and method == "GET":
            return JSONResponse(_public_settings(context))

        if path == "/api/session/settings" and method == "PUT":
            try:
                payload = await request.json()
            except Exception:
                return JSONResponse({"detail": "Session settings must be valid JSON."}, status_code=400)
            if not isinstance(payload, dict):
                return JSONResponse({"detail": "Session settings must be an object."}, status_code=400)

            if "display_name" in payload:
                context.session.display_name = str(payload.get("display_name") or "")[:120]
            if payload.get("locale") in {"en", "fr"}:
                context.session.locale = payload["locale"]
            if payload.get("theme") in {"system", "dark", "light"}:
                context.session.theme = payload["theme"]
            if "worker_url" in payload:
                context.session.worker_url = str(payload.get("worker_url") or "").strip() or None
                _replace_worker_backend(context, context.session.worker_url)
            if "neuronpedia_api_key" in payload:
                api_key = str(payload.get("neuronpedia_api_key") or "").strip() or None
                context.session.neuronpedia_api_key = api_key
                # A stored key is only configured, never connected until tested.
                context.session.neuronpedia_connected = False
                _replace_neuronpedia_backend(context, api_key)

            return JSONResponse(_public_settings(context))

        if path == "/api/session/neuronpedia-key" and method == "DELETE":
            context.session.neuronpedia_api_key = None
            context.session.neuronpedia_connected = False
            _replace_neuronpedia_backend(context, None)
            return JSONResponse(_public_settings(context))

        if path == "/api/session/neuronpedia/test" and method == "POST":
            try:
                payload = await request.json()
            except Exception:
                payload = {}
            if not isinstance(payload, dict):
                payload = {}

            supplied = payload.get("neuronpedia_api_key")
            api_key = str(supplied or context.session.neuronpedia_api_key or "").strip()
            if not api_key:
                context.session.neuronpedia_connected = False
                return JSONResponse(
                    {
                        **_public_settings(context),
                        "message": _localized(
                            context,
                            fr="Aucune clé API fournie ; les démos et imports restent disponibles.",
                            en="No API key supplied; demo and imports remain available.",
                        ),
                        "upstream_status": None,
                    }
                )

            try:
                async with httpx.AsyncClient(
                    base_url=context.settings.neuronpedia_base_url,
                    timeout=10,
                    follow_redirects=True,
                ) as client:
                    response = await client.get("/api/health", headers={"x-api-key": api_key})
                status = int(response.status_code)
            except httpx.HTTPError:
                context.session.neuronpedia_api_key = api_key
                context.session.neuronpedia_connected = False
                _replace_neuronpedia_backend(context, api_key)
                return JSONResponse(
                    {
                        **_public_settings(context),
                        "message": _localized(
                            context,
                            fr="Neuronpedia est injoignable ; les démos et imports restent disponibles.",
                            en="Neuronpedia is unreachable; demo and imports remain available.",
                        ),
                        "upstream_status": None,
                    }
                )

            connected = 200 <= status < 300
            context.session.neuronpedia_api_key = api_key
            context.session.neuronpedia_connected = connected
            _replace_neuronpedia_backend(context, api_key)

            if connected:
                message = _localized(
                    context,
                    fr="Neuronpedia a répondu correctement ; la clé est activée pour cette session.",
                    en="Neuronpedia responded successfully; the key is enabled for this session.",
                )
            elif status in {401, 403}:
                message = _localized(
                    context,
                    fr=f"Neuronpedia a refusé la clé API (HTTP {status}).",
                    en=f"Neuronpedia rejected the API key (HTTP {status}).",
                )
            else:
                message = _localized(
                    context,
                    fr=f"Le test de connexion Neuronpedia a échoué (HTTP {status}).",
                    en=f"Neuronpedia connection test failed (HTTP {status}).",
                )

            return JSONResponse(
                {
                    **_public_settings(context),
                    "message": message,
                    "upstream_status": status,
                }
            )

        return await call_next(request)

    app.state.prismora_session_security_installed = True
