"""The benchmark dataset tools through the SDK's in-memory client, with the
`benchmark_data` calls faked."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from mcp import Client
from mcp.server.mcpserver import MCPServer
from mcp.types import CallToolResult, TextContent

from app.modules.activities import ActivitySource
from app.modules.benchmark_data import (
    Band,
    BandEdit,
    BenchmarkDataset,
    Editor,
    InvalidEditError,
    Metric,
    PeerCut,
    PeerCutEdit,
    UnknownRecordError,
)
from app.modules.mcp.api.tools import benchmark
from app.modules.mcp.bootstrap import build_server
from app.modules.mcp.domain.access import Caller
from app.modules.mcp.persistence.adapters import InMemoryToolCallAudit

_CALLER = Caller(slack_user_id="U_ALICE", team_id="T1", name="Alice Jones", scopes=("crm",))
_THEN = datetime(2026, 11, 1, tzinfo=UTC)
_NOW = datetime(2026, 11, 15, tzinfo=UTC)
_SALON = PeerCut(
    uuid4(), "sme", "salon", "Salon", 48, True, False, {"gm": (62, 68, 74, 79, 84)}, "Ramzy", _NOW
)
_BAND = Band(uuid4(), "micro", "Under 1m", 1_000_000, -3, 0.8, 1.25, "seed", _THEN)
_GM = Metric(uuid4(), "gm", "Gross margin", "%", True, 100, None, "Jules", _NOW)
_DATASET = BenchmarkDataset(
    updated_at=_NOW,
    bands=(_BAND, Band(uuid4(), "top", "Top", None, 4, 1.4, 0.8, "seed", _THEN)),
    metrics={
        "sme": {"gm": _GM},
        "tech": {
            "growth": Metric(uuid4(), "growth", "Growth", "%", True, 100, True, "seed", _THEN)
        },
    },
    cuts={"sme": {"salon": _SALON}, "tech": {}},
)


def _text(result: CallToolResult) -> str:
    return " ".join(c.text for c in result.content if isinstance(c, TextContent))


def _server() -> MCPServer:
    return build_server(
        public_url="https://tools.example",
        token_secret="secret",
        calls_per_hour=100,
        caller_source=lambda: _CALLER,
        audit=InMemoryToolCallAudit(),
    )


async def test_overview_shows_who_last_changed_each_row(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(benchmark, "load_dataset", AsyncMock(return_value=_DATASET))
    async with Client(_server()) as client:
        result = await client.call_tool("get_benchmark_overview", {})

    out = result.structured_content
    assert out is not None
    assert "dataset_version" not in out
    assert out["dataset_updated_at"].startswith("2026-11-15")
    assert out["sme_metrics"][0]["weight"] == 100
    assert out["sme_metrics"][0]["updated_by"] == "Jules"
    assert [(b["code"], b["updated_by"]) for b in out["bands"]] == [
        ("micro", "seed"),
        ("top", "seed"),
    ]
    assert out["peer_cuts"][0]["key"] == "salon"
    assert out["peer_cuts"][0]["updated_by"] == "Ramzy"


async def test_get_peer_cut_returns_the_anchors_and_the_last_editor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(benchmark, "load_dataset", AsyncMock(return_value=_DATASET))
    async with Client(_server()) as client:
        result = await client.call_tool("get_peer_cut", {"mode": "sme", "key": "salon"})

    assert result.structured_content is not None
    assert result.structured_content["anchors"] == {"gm": [62, 68, 74, 79, 84]}
    assert result.structured_content["updated_by"] == "Ramzy"
    assert result.structured_content["updated_at"].startswith("2026-11-15")


async def test_an_unknown_peer_cut_says_where_to_look(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(benchmark, "load_dataset", AsyncMock(return_value=_DATASET))
    async with Client(_server()) as client:
        result = await client.call_tool("get_peer_cut", {"mode": "sme", "key": "nope"})
    assert result.is_error
    assert "get_benchmark_overview" in _text(result)


async def test_edit_peer_cut_saves_once_per_request_id_as_the_named_person(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    edit = AsyncMock(return_value=_SALON)
    monkeypatch.setattr(benchmark, "edit_peer_cut", edit)
    args = {
        "mode": "sme",
        "key": "salon",
        "sample_size": 60,
        "anchors": {"gm": [63, 69, 75, 80, 85]},
        "request_id": "req-00001",
    }

    async with Client(_server()) as client:
        first = await client.call_tool("edit_benchmark_peer_cut", args)
        retry = await client.call_tool("edit_benchmark_peer_cut", args)

    assert first.structured_content == retry.structured_content
    edit.assert_awaited_once()
    assert edit.await_args is not None
    assert edit.await_args.args == (
        "sme",
        "salon",
        PeerCutEdit(sample_size=60, anchors={"gm": (63, 69, 75, 80, 85)}),
    )
    assert edit.await_args.kwargs == {
        "editor": Editor(slack_user_id="U_ALICE", name="Alice Jones"),
        "source": ActivitySource.MCP,
    }


async def test_anchors_need_exactly_five_numbers() -> None:
    async with Client(_server()) as client:
        result = await client.call_tool(
            "edit_benchmark_peer_cut",
            {
                "mode": "sme",
                "key": "salon",
                "anchors": {"gm": [1, 2, 3]},
                "request_id": "req-00002",
            },
        )
    assert result.is_error


async def test_a_refused_edit_says_nothing_was_saved(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        benchmark,
        "edit_peer_cut",
        AsyncMock(side_effect=InvalidEditError("gm: anchors must rise from p10 to p90")),
    )
    async with Client(_server()) as client:
        result = await client.call_tool(
            "edit_benchmark_peer_cut",
            {
                "mode": "sme",
                "key": "salon",
                "anchors": {"gm": [9, 8, 7, 6, 5]},
                "request_id": "req-00003",
            },
        )
    assert result.is_error
    assert "Nothing was saved: gm: anchors must rise" in _text(result)


async def test_edit_revenue_band_passes_only_the_fields_sent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    edit = AsyncMock(return_value=(_BAND,))
    monkeypatch.setattr(benchmark, "edit_band", edit)
    async with Client(_server()) as client:
        result = await client.call_tool(
            "edit_revenue_band",
            {"code": "micro", "ebitda_adj": -2.5, "request_id": "req-00004"},
        )

    assert result.structured_content is not None
    assert result.structured_content["bands"][0]["code"] == "micro"
    assert edit.await_args is not None
    assert edit.await_args.args == ("micro", BandEdit(ebitda_adj=-2.5))
    assert edit.await_args.kwargs["editor"].name == "Alice Jones"


async def test_an_unknown_band_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        benchmark, "edit_band", AsyncMock(side_effect=UnknownRecordError("No revenue band 'huge'"))
    )
    async with Client(_server()) as client:
        result = await client.call_tool(
            "edit_revenue_band", {"code": "huge", "label": "x", "request_id": "req-00005"}
        )
    assert result.is_error
    assert "No revenue band 'huge'" in _text(result)


async def test_set_metric_weights_returns_the_metrics_with_their_editor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    save = AsyncMock(return_value={"gm": _GM})
    monkeypatch.setattr(benchmark, "set_weights", save)
    async with Client(_server()) as client:
        result = await client.call_tool(
            "set_metric_weights", {"mode": "sme", "weights": {"gm": 100}, "request_id": "req-00006"}
        )

    assert result.structured_content is not None
    assert result.structured_content["mode"] == "sme"
    assert result.structured_content["metrics"][0]["key"] == "gm"
    assert result.structured_content["metrics"][0]["updated_by"] == "Jules"
    assert save.await_args is not None
    assert save.await_args.args == ("sme", {"gm": 100})


async def test_the_edit_tools_tell_claude_to_read_first_and_name_the_person() -> None:
    async with Client(_server()) as client:
        tools = {t.name: t.description or "" for t in (await client.list_tools()).tools}

    for name in ("edit_benchmark_peer_cut", "edit_revenue_band", "set_metric_weights"):
        assert "signed-in person's name" in tools[name]
        assert "who last changed" in tools[name]
