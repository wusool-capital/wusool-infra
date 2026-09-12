"""Every slash command must open its modal before it queries anything.

Slack invalidates a `trigger_id` 3s after the command is issued, and that
clock starts before the request reaches us — so any database work done before
`views_open` is charged against it. `/edit-buyer` died in production with
`expired_trigger_id` after a 2071ms handler: well inside 3s as measured from
the handler, not as measured from the command.

Two checks, because neither alone is enough:

1. `test_*_opens_modal_before_querying` drives a real handler and asserts the
   observed call order. Proves the behaviour, but can only reach handlers that
   are importable — matching-engine's is a closure inside `register()`.
2. `test_every_command_handler_opens_before_it_queries` reads the AST of all
   three command modules, so a *new* command, or a closure this file can't
   call, cannot quietly reintroduce the bug. Mirrors the AST fitness tests in
   `test_architecture.py`.
"""

import ast
from pathlib import Path

import pytest

_SERVER_ROOT = Path(__file__).resolve().parents[1]
_COMMAND_MODULES = (
    "app/modules/ddl_commands/api/slack/handlers/commands.py",
    "app/modules/matching_engine/api/slack/handlers/commands.py",
    "app/modules/enrichment/api/slack/handlers/commands.py",
)
# Anything that reaches Postgres before the modal is open is the bug.
_QUERY_CALLS = {
    "resolve_buyer",
    "resolve_seller",
    "search_organizations",
    "resolve_org_roles",
}
_OPEN_CALL = "open_loading_modal"


def _called_names(node: ast.AST) -> list[tuple[int, str]]:
    out = []
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            func = child.func
            name = getattr(func, "id", None) or getattr(func, "attr", None)
            if name:
                out.append((child.lineno, name))
    return out


@pytest.mark.parametrize("module_path", _COMMAND_MODULES)
def test_every_command_handler_opens_before_it_queries(module_path: str) -> None:
    tree = ast.parse((_SERVER_ROOT / module_path).read_text(encoding="utf-8"))
    offenders = []
    for func in ast.walk(tree):
        if not isinstance(func, (ast.AsyncFunctionDef, ast.FunctionDef)):
            continue
        calls = _called_names(func)
        queries = [(line, n) for line, n in calls if n in _QUERY_CALLS]
        if not queries:
            continue
        opens = [line for line, n in calls if n == _OPEN_CALL]
        if not opens:
            offenders.append(f"{func.name}: queries {queries[0][1]!r} but never opens a modal")
        elif min(opens) > min(line for line, _ in queries):
            offenders.append(f"{func.name}: queries {queries[0][1]!r} before opening the modal")
    assert not offenders, f"{module_path}: {offenders}"


class _RecordingClient:
    """Records the order of Slack calls; `views_open` returns a `view_id` the
    way the real client does so the handler can go on to `views_update`.
    """

    def __init__(self, calls: list[str]) -> None:
        self._calls = calls

    async def views_open(self, **_: object) -> dict:
        self._calls.append("views_open")
        return {"view": {"id": "V_TEST"}}

    async def views_update(self, **_: object) -> dict:
        self._calls.append("views_update")
        return {"ok": True}

    async def chat_postEphemeral(self, **_: object) -> dict:  # noqa: N802 - Slack's name
        self._calls.append("chat_postEphemeral")
        return {"ok": True}


@pytest.mark.asyncio
async def test_edit_buyer_opens_modal_before_querying(monkeypatch) -> None:
    from app.modules.ddl_commands.api.slack.handlers import commands

    calls: list[str] = []

    async def fake_resolve_buyer(name: str):  # noqa: ANN202
        calls.append("resolve_buyer")
        raise AssertionError("stop here — ordering is all this test cares about")

    monkeypatch.setattr(commands, "resolve_buyer", fake_resolve_buyer)

    with pytest.raises(AssertionError, match="stop here"):
        await commands._handle_buyer_command(
            {
                "text": "Acme",
                "channel_id": "C",
                "user_id": "U",
                "trigger_id": "trigger.ordering-test",
            },
            _RecordingClient(calls),
            action="edit_buyer",
        )

    assert calls == ["views_open", "resolve_buyer"], calls
