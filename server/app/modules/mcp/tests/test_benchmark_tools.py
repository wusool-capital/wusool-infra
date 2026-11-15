"""The benchmark dataset tools through the SDK's in-memory client, with the
`benchmark_data` calls faked."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from mcp import Client
from mcp.server.mcpserver import MCPServer
from mcp.types import CallToolResult, TextContent

from app.modules.benchmark_data import (
    Band,
    BandEdit,
    BenchmarkDataset,
    Edited,
    InvalidEditError,
    Metric,
    PeerCut,
    PeerCutEdit,
    UnknownRecordError,
)
from app.modules.mcp.api.tools import benchmark
from app.modules.mcp.bootstrap import build_server
from app.modules.mcp.domain.access import Caller

_CALLER = Caller(slack_user_id="U_ALICE", team_id="T1", name="Alice", scopes=("crm",))
_SALON = PeerCut("sme", "salon", "Salon", 48, True, False, {"gm": (62, 68, 74, 79, 84)})
_BAND = Band("micro", "Under 1m", 1_000_000, -3, 0.8, 1.25)
_DATASET = BenchmarkDataset(
    version=3,
    updated_at=datetime(2026, 11, 15, tzinfo=UTC),
    bands=(_BAND, Band("top", "Top", None, 4, 1.4, 0.8)),
    metrics={
        "sme": {"gm": Metric("gm", "Gross margin", "%", True, 100, None)},
        "tech": {"growth": Metric("growth", "Growth", "%", True, 100, True)},
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
    )


async def test_overview_lists_bands_weights_and_peer_cuts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(benchmark, "load_dataset", AsyncMock(return_value=_DATASET))
    async with Client(_server()) as client:
        result = await client.call_tool("get_benchmark_overview", {})

    out = result.structured_content
    assert out is not None
    assert out["dataset_version"] == 3
    assert out["sme_metrics"][0]["weight"] == 100
    assert [b["id"] for b in out["bands"]] == ["micro", "top"]
    assert out["peer_cuts"] == [
        {
            "mode": "sme",
            "key": "salon",
            "label": "Salon",
            "sample_size": 48,
            "multi_site": True,
            "b2b": False,
        }
    ]


async def test_get_peer_cut_returns_the_anchors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(benchmark, "load_dataset", AsyncMock(return_value=_DATASET))
    async with Client(_server()) as client:
        result = await client.call_tool("get_peer_cut", {"mode": "sme", "key": "salon"})

    assert result.structured_content is not None
    assert result.structured_content["anchors"] == {"gm": [62, 68, 74, 79, 84]}


async def test_an_unknown_peer_cut_says_where_to_look(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(benchmark, "load_dataset", AsyncMock(return_value=_DATASET))
    async with Client(_server()) as client:
        result = await client.call_tool("get_peer_cut", {"mode": "sme", "key": "nope"})
    assert result.is_error
    assert "get_benchmark_overview" in _text(result)


async def test_edit_peer_cut_saves_once_per_request_id_under_the_callers_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    edit = AsyncMock(return_value=Edited(_SALON, 4))
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
    assert first.structured_content is not None
    assert first.structured_content["dataset_version"] == 4
    edit.assert_awaited_once()
    assert edit.await_args is not None
    assert edit.await_args.args == (
        "sme",
        "salon",
        PeerCutEdit(sample_size=60, anchors={"gm": (63, 69, 75, 80, 85)}),
    )
    assert edit.await_args.kwargs == {"edited_by": "Alice"}


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
    edit = AsyncMock(return_value=Edited((_BAND,), 5))
    monkeypatch.setattr(benchmark, "edit_band", edit)
    async with Client(_server()) as client:
        result = await client.call_tool(
            "edit_revenue_band",
            {"band_id": "micro", "ebitda_adj": -2.5, "request_id": "req-00004"},
        )

    assert result.structured_content is not None
    assert result.structured_content["dataset_version"] == 5
    assert edit.await_args is not None
    assert edit.await_args.args == ("micro", BandEdit(ebitda_adj=-2.5))


async def test_an_unknown_band_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        benchmark, "edit_band", AsyncMock(side_effect=UnknownRecordError("No revenue band 'huge'"))
    )
    async with Client(_server()) as client:
        result = await client.call_tool(
            "edit_revenue_band", {"band_id": "huge", "label": "x", "request_id": "req-00005"}
        )
    assert result.is_error
    assert "No revenue band 'huge'" in _text(result)


async def test_set_metric_weights(monkeypatch: pytest.MonkeyPatch) -> None:
    weights = {"gm": 100}
    save = AsyncMock(return_value=Edited(weights, 6))
    monkeypatch.setattr(benchmark, "set_weights", save)
    async with Client(_server()) as client:
        result = await client.call_tool(
            "set_metric_weights", {"mode": "sme", "weights": weights, "request_id": "req-00006"}
        )

    assert result.structured_content == {"mode": "sme", "weights": weights, "dataset_version": 6}
    assert save.await_args is not None
    assert save.await_args.args == ("sme", weights)
