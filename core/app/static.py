"""Serve the built console and resident apps from one folder, for a single-service deploy.

`$STATIC_DIR/console` is mounted at `/console` and `$STATIC_DIR/resident` at `/`; both fall back to their own
`index.html` so client-side routes survive a reload. API paths never fall back: an unknown `/v1/...` stays a JSON 404.
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from starlette.exceptions import HTTPException
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

NEVER_FALL_BACK = ("v1/", "assets/")
IMMUTABLE = "public, max-age=31536000, immutable"


def file_like(path: str) -> bool:
    """A missing `favicon.svg` or `x.js` is a 404, not the app shell. Starlette names the mount root `.`."""
    return path != "." and "." in path.rsplit("/", 1)[-1]


class SpaFiles(StaticFiles):
    async def get_response(self, path: str, scope: Scope):
        try:
            response = await super().get_response(path, scope)
        except HTTPException as error:
            if error.status_code != 404 or path.startswith(NEVER_FALL_BACK) or path in ("healthz", "v1") or file_like(path):
                raise
            path = "index.html"
            response = await super().get_response(path, scope)
        if path.endswith("index.html"):
            response.headers["Cache-Control"] = "no-cache"
        elif path.startswith("assets/"):
            response.headers["Cache-Control"] = IMMUTABLE
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        return response


def install(app: FastAPI, static_dir: str) -> None:
    """Add the static mounts. Call last, so every API route is matched before the catch-all at `/`."""
    root = Path(static_dir)
    app.add_api_route("/console", lambda: RedirectResponse("/console/"), include_in_schema=False)
    app.mount("/console", SpaFiles(directory=root / "console"), name="console")
    app.mount("/", SpaFiles(directory=root / "resident"), name="resident")
