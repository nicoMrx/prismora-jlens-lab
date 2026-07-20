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

        package_root = Path(__file__).resolve().parents[2]
        mount_campaign_routes(self, context, package_root)
        mount_demo_library_routes(self, package_root)

        static_root = Path(getattr(app, "directory", package_root / "web"))
        guard_tag = '<script src="/v4-sidebar-observer-guard.js?v=1"></script>'

        @self.get("/v4.html", include_in_schema=False)
        async def prismora_v4_guarded() -> HTMLResponse:
            html_path = static_root / "v4.html"
            html = html_path.read_text(encoding="utf-8")
            if guard_tag not in html:
                marker = '<script src="/v4-campaign-center.js'
                if marker not in html:
                    marker = '<script src="/v4-token-tooltip.js'
                html = html.replace(marker, guard_tag + marker, 1)
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
