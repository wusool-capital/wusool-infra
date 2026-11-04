"""Serves the built web app (`client/dist`) under `/app`.

Client-side routes (`/app/runs/<id>`) have no file behind them, so a miss on
a route path falls back to `index.html`; a miss on a file path (an old hashed
asset) stays a 404 rather than returning HTML where a script was expected.
"""

from pathlib import Path, PurePosixPath

from fastapi import FastAPI, Request
from starlette.exceptions import HTTPException
from starlette.responses import RedirectResponse, Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

# Vite content-hashes everything under assets/, so it can be cached for good;
# index.html must always be revalidated so a deploy is picked up at once.
_IMMUTABLE = "public, max-age=31536000, immutable"
_NO_CACHE = "no-cache"


class SpaStatic(StaticFiles):
    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            response = await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code != 404 or PurePosixPath(path).suffix:
                raise
            response = await super().get_response("index.html", scope)
        is_asset = PurePosixPath(path).parts[:1] == ("assets",)
        response.headers["Cache-Control"] = _IMMUTABLE if is_asset else _NO_CACHE
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response


def web_app_dist(server_root: Path) -> Path | None:
    """The image copies the build next to `main.py`; a checkout builds it in `client/`."""
    for candidate in (server_root / "client-dist", server_root.parent / "client" / "dist"):
        if (candidate / "index.html").is_file():
            return candidate
    return None


def mount_web_app(app: FastAPI, directory: Path) -> None:
    """Mounts the app at `/app/`. A mount only matches below the slash, so the bare
    `/app` people type would fall through to the catch-all and 404."""

    @app.get("/app", include_in_schema=False)
    async def web_app_root(request: Request) -> RedirectResponse:
        query = f"?{request.url.query}" if request.url.query else ""
        return RedirectResponse(f"/app/{query}", status_code=308)

    app.mount("/app", SpaStatic(directory=directory, html=True), name="web_app")
