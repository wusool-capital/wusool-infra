"""Server entrypoint. Not the plain `uvicorn main:app` CLI invocation:
uvicorn's CLI configures its own logging (dictConfig) before importing the
app, giving `uvicorn`/`uvicorn.access` their own non-propagating handlers.
That silently defeats `app.shared.logging.configure_logging()` — those
two loggers' lines never reach our JSON formatter. `log_config=None` skips
uvicorn's dictConfig entirely, so those loggers fall through to root's
handler like everything else.
"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, log_config=None)
