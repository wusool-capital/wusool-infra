"""Process-wide logging configuration, shared by matching-engine and
ddl-commands (previously two byte-identical copies of this file).

Every log line is a single JSON object carrying: timestamp, level, the
owning service (derived from the logger name), logger name, message,
exception info (if any), and whatever request context is active (see
`log_context`).

Callers MUST disable uvicorn's own logging config (`log_config=None`)
when starting the server — otherwise uvicorn installs non-propagating
handlers directly on the `uvicorn`/`uvicorn.access` loggers and their
lines never reach this formatter. See the executable entrypoint in `main.py`.
"""

import contextvars
import json
import logging
from typing import Any

# Every module logger is named `app.modules.<module>.*` since the repo
# restructure merged what used to be two separate top-level packages
# (`app`/`ddl_commands`) into one. A bare top-level-package check would
# make every logger's top-level component `"app"` regardless of which
# module emitted it — this maps the third path segment instead.
_SERVICE_BY_MODULE: dict[str, str] = {
    "matching_engine": "matching-engine",
    "ddl_commands": "ddl-commands",
}
# Third-party loggers, which aren't under `app.modules.*` at all.
_SERVICE_BY_TOP_LEVEL_PACKAGE: dict[str, str] = {
    "slack_bolt": "slack-bolt",
}
_UNTAGGED_SERVICE = "other"


def _service_for(logger_name: str) -> str:
    parts = logger_name.split(".")
    if len(parts) >= 3 and parts[0] == "app" and parts[1] == "modules":
        return _SERVICE_BY_MODULE.get(parts[2], _UNTAGGED_SERVICE)
    return _SERVICE_BY_TOP_LEVEL_PACKAGE.get(parts[0], _UNTAGGED_SERVICE)


# Request-scoped fields (Slack trigger, user, channel, ...), set once per
# incoming request/event and read by every log line emitted while handling
# it. None outside a request — a mutable dict default would be shared
# across every context that never calls .set().
log_context: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
    "log_context", default=None
)


class ContextFilter(logging.Filter):
    """Tags every record with its owning service and the active request context."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.service = _service_for(record.name)
        record.context = log_context.get() or {}
        return True


class JsonFormatter(logging.Formatter):
    """One JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "service": getattr(record, "service", _UNTAGGED_SERVICE),
            "logger": record.name,
            "message": record.getMessage(),
        }
        payload.update(getattr(record, "context", None) or {})
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(log_level: str) -> None:
    """Configure root logging once, at application startup."""
    handler = logging.StreamHandler()
    handler.addFilter(ContextFilter())
    handler.setFormatter(JsonFormatter())

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    root_logger.handlers = [handler]
