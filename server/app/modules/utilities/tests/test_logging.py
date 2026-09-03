"""`ContextFilter`'s service-attribution — the fix for a real bug where every
logger name is `app.modules.<module>.*` post-restructure (both modules used
to be separate top-level packages), so a bare top-level-package check
tagged every log line from both modules as the same service.
"""

import logging

from app.modules.utilities.domain.logging import _service_for


def test_matching_engine_logger_is_tagged_correctly() -> None:
    assert _service_for("app.modules.matching_engine.bootstrap") == "matching-engine"


def test_ddl_commands_logger_is_tagged_correctly() -> None:
    assert _service_for("app.modules.ddl_commands.attio_sync") == "ddl-commands"


def test_third_party_logger_is_tagged_by_top_level_package() -> None:
    assert _service_for("slack_bolt.App") == "slack-bolt"


def test_unrecognized_logger_falls_back_to_other() -> None:
    assert _service_for("httpx") == "other"
    assert _service_for("app.modules.utilities.persistence.engine") == "other"


def test_context_filter_sets_service_attribute() -> None:
    from app.modules.utilities.domain.logging import ContextFilter

    record = logging.LogRecord(
        name="app.modules.ddl_commands.bootstrap",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="test",
        args=(),
        exc_info=None,
    )
    assert ContextFilter().filter(record) is True
    assert getattr(record, "service", None) == "ddl-commands"
