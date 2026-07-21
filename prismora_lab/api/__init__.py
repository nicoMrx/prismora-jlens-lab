"""FastAPI control plane and Prismora extension registration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse


_ORIGINAL_MOUNT = FastAPI.mount


def _mount_with_prismora_extensions(
    self: FastAPI,
    path: str,
    app: Any,
    name: str | None = None,
) -> Any:
    """Attach Prismora routes immediately before the root static mount.

    `create_app` intentionally keeps the core API compact. Extensions register
    here only for the Prismora application and only once per app instance.
    """

    is_prismora = getattr(self, "title", None) == "Prismora J-Lens Lab"
    context = getattr(self.state, "lab", None)
    already_mounted = getattr(self.state, "prismora_extensions_mounted", False)
    if path == "/" and is_prismora and context is not None and not already_mounted:
        from ..campaign_api import mount_campaign_routes
        from ..demo_library_api import mount_demo_library_routes
        from ..live_chat import mount_live_chat_routes
        from ..session_security import install_session_security

        package_root = Path(__file__).resolve().parents[2]
        install_session_security(self, context)
        mount_live_chat_routes(self, context)
        mount_campaign_routes(self, context, package_root)
        mount_demo_library_routes(self, package_root)

        static_root = Path(getattr(app, "directory", package_root / "web"))
        extension_styles = (
            '<link rel="stylesheet" href="/v4-contest-title.css?v=1" data-prismora-contest-title="1">',
            '<link rel="stylesheet" href="/v4-live-chat.css?v=1" data-prismora-live-chat-style="1">',
            '<link rel="stylesheet" href="/v4-campaign-polish.css?v=1" data-prismora-campaign-polish="1">',
            '<link rel="stylesheet" href="/v4-showcase-insights.css?v=1" data-prismora-showcase-insights="1">',
        )
        extension_scripts = (
            '<script src="/v4-sidebar-observer-guard.js?v=1"></script>',
            '<script src="/v4-connection-semantics.js?v=1" data-prismora-connection-semantics="1"></script>',
            '<script src="/v4-live-chat.js?v=1" data-prismora-live-chat="1"></script>',
            '<script src="/v4-campaign-polish.js?v=1" data-prismora-campaign-polish="1"></script>',
            '<script src="/v4-showcase-insights.js?v=1" data-prismora-showcase-insights="1"></script>',
        )

        @self.get("/v4.html", include_in_schema=False)
        async def prismora_v4_guarded() -> HTMLResponse:
            html_path = static_root / "v4.html"
            html = html_path.read_text(encoding="utf-8")
            missing_styles = "".join(tag for tag in extension_styles if tag not in html)
            if missing_styles:
                html = html.replace("</head>", missing_styles + "</head>", 1)

            marker = '<script src="/v4-campaign-center.js'
            if marker not in html:
                marker = '<script src="/v4-token-tooltip.js'
            missing_scripts = "".join(tag for tag in extension_scripts if tag not in html)
            if missing_scripts:
                html = html.replace(marker, missing_scripts + marker, 1)

            return HTMLResponse(
                html,
                headers={
                    "Cache-Control": "no-store, no-cache, must-revalidate",
                    "Pragma": "no-cache",
                },
            )

        self.state.prismora_extensions_mounted = True
    return _ORIGINAL_MOUNT(self, path, app, name=name)


if FastAPI.mount is not _mount_with_prismora_extensions:
    FastAPI.mount = _mount_with_prismora_extensions
