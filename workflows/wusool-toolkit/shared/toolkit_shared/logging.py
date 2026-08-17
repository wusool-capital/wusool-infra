"""Process-wide logging configuration, shared by matching-engine and
ddl-commands (previously two byte-identical copies of this file).

Every log line is tagged with a `service` field derived from the logger
name's top-level package, so a CloudWatch query can filter by
matching-engine vs ddl-commands vs Slack Bolt's own internal logging.
"""

import logging

_SERVICE_BY_TOP_LEVEL_PACKAGE: dict[str, str] = {
    "app": "matching-engine",
    "ddl_commands": "ddl-commands",
    "slack_bolt": "slack-bolt",
}
_UNTAGGED_SERVICE = "other"

_LOG_FORMAT = "%(asctime)s %(levelname)s [%(service)s] [%(name)s] %(message)s"


class ServiceTagFilter(logging.Filter):
    """Adds a `service` attribute to every record it sees."""

    def filter(self, record: logging.LogRecord) -> bool:
        top_level_package = record.name.split(".", 1)[0]
        record.service = _SERVICE_BY_TOP_LEVEL_PACKAGE.get(top_level_package, _UNTAGGED_SERVICE)
        return True


def configure_logging(log_level: str) -> None:
    """Configure root logging once, at application startup."""
    handler = logging.StreamHandler()
    handler.addFilter(ServiceTagFilter())
    handler.setFormatter(logging.Formatter(_LOG_FORMAT))

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    root_logger.handlers = [handler]
