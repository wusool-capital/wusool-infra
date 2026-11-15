"""`GET /benchmark/20-data.js`: the page's `DATA`, rendered from the tables.

Registered ahead of the static mount, so it shadows the file of the same name.
That file stays as the fallback copy for when the database cannot be read.
"""

import logging
import time

from fastapi import APIRouter
from starlette.responses import Response

from app.modules.benchmark_data import load_dataset
from app.modules.lead_magnets.api.benchmark.dataset_js import render_dataset_js
from app.modules.lead_magnets.api.static import static_dir
from app.modules.lead_magnets.domain.benchmark.benchmark_dataset import TECH_SECTOR_LIST

logger = logging.getLogger(__name__)

router = APIRouter(tags=["lead-magnets"])

# Same lifetime as the other static assets, so an advisor's edit reaches
# visitors within a minute.
_HEADERS = {"Cache-Control": "public, max-age=60", "X-Content-Type-Options": "nosniff"}

# The route is public, so one render serves every request for this long instead of two table
# reads each. Only a successful render is kept. Per process, which is right for one instance.
_CACHE_SECONDS = 30.0
_clock = time.monotonic
_cached: tuple[float, str] | None = None


@router.get("/benchmark/20-data.js", include_in_schema=False)
async def benchmark_dataset_script() -> Response:
    global _cached
    now = _clock()
    if _cached is not None and now - _cached[0] < _CACHE_SECONDS:
        return Response(_cached[1], media_type="text/javascript", headers=_HEADERS)
    try:
        script = render_dataset_js(await load_dataset(), TECH_SECTOR_LIST)
        _cached = (now, script)
    except Exception:
        # A blank benchmark page is worse than slightly stale peer data. Never cached, so
        # the edited numbers return as soon as the database does.
        logger.exception("benchmark_dataset_script_fallback")
        script = (static_dir() / "benchmark" / "20-data.js").read_text(encoding="utf-8")
        return Response(
            script, media_type="text/javascript", headers={**_HEADERS, "Cache-Control": "no-store"}
        )
    return Response(script, media_type="text/javascript", headers=_HEADERS)
