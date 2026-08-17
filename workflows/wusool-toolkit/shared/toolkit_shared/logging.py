"""Process-wide logging configuration, shared by matching-engine and
ddl-commands (previously two byte-identical copies of this file).

Every log line is a single JSON object carrying: timestamp, level, the
owning service (derived from the logger name's top-level package),
logger name, message, exception info (if any), and whatever request
context is active (see `log_context`).

Callers MUST disable uvicorn's own logging config (`log_config=None`)
when starting the server — otherwise uvicorn installs non-propagating
handlers directly on the `uvicorn`/`uvicorn.access` loggers and their
lines never reach this formatter. See `run.py`.
"""

import contextvars
import json
import logging
from typing import Any

_SERVICE_BY_TOP_LEVEL_PACKAGE: dict[str, str] = {
    "app": "matching-engine",
    "ddl_commands": "ddl-commands",
    "slack_bolt": "slack-bolt",
}
_UNTAGGED_SERVICE = "other"

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
        top_level_package = record.name.split(".", 1)[0]
        record.service = _SERVICE_BY_TOP_LEVEL_PACKAGE.get(top_level_package, _UNTAGGED_SERVICE)
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
