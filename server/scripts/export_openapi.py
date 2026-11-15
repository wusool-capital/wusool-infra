"""Writes an OpenAPI spec for a frontend to generate its typed client from
(`npm run gen:api`). Only that frontend's routers are included, so a client never
sees the Slack, Attio, or desktop surfaces, and no live server or database is needed.

`web` (default) is the find-match API for `client/`; `engine` is `/api/v1` for
`engine-frontend/`.

Usage: uv run python scripts/export_openapi.py ../client/openapi.json
       uv run python scripts/export_openapi.py ../engine-frontend/openapi.json --app engine
"""

import argparse
import json
from pathlib import Path

from fastapi import FastAPI

from app.modules.crm import router as crm_router
from app.modules.engine import router as engine_router
from app.modules.matching_engine.api.http.auth_routes import router as auth_router
from app.modules.matching_engine.api.http.routes import router


def build_app(name: str) -> FastAPI:
    if name == "engine":
        app = FastAPI(title="Wusool Engine API", version="1")
        app.include_router(crm_router)
        app.include_router(engine_router)
        return app
    app = FastAPI(title="Wusool web API", version="1")
    app.include_router(auth_router)
    app.include_router(router)
    return app


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("output", type=Path)
    parser.add_argument("--app", choices=("web", "engine"), default="web")
    args = parser.parse_args()
    spec = json.dumps(build_app(args.app).openapi(), indent=2, sort_keys=True)
    args.output.write_text(spec + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
