"""Writes the web find-match API's OpenAPI spec for `client/` to generate its
typed client from (`npm run gen:api`). Only the `/api` router is included, so
the client never sees the Slack, Attio, or desktop surfaces, and no live
server or database is needed.

Usage: uv run python scripts/export_openapi.py ../client/openapi.json
"""

import json
import sys
from pathlib import Path

from fastapi import FastAPI

from app.modules.matching_engine.api.http.auth_routes import router as auth_router
from app.modules.matching_engine.api.http.routes import router


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: export_openapi.py <output-path>")
    app = FastAPI(title="Wusool web API", version="1")
    app.include_router(auth_router)
    app.include_router(router)
    spec = json.dumps(app.openapi(), indent=2, sort_keys=True)
    Path(sys.argv[1]).write_text(spec + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
