"""Read and edit the GCC SME Benchmark's peer dataset: the revenue bands, the
metric weights and each peer set's percentile anchors. Edits change what
visitors are scored against straight away."""

from collections.abc import Mapping
from typing import Annotated

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

from app.modules.benchmark_data import (
    Anchors,
    Band,
    BandEdit,
    BenchmarkDataset,
    Metric,
    PeerCut,
    PeerCutEdit,
    UnknownRecordError,
    edit_band,
    edit_peer_cut,
    load_dataset,
    set_weights,
)
from app.modules.mcp.api.runner import ToolRunner
from app.modules.mcp.api.tools.schemas import (
    AnchorList,
    BandOut,
    BandsEdited,
    BenchmarkOverview,
    MetricOut,
    ModeParam,
    PeerCutEdited,
    PeerCutOut,
    PeerCutSummary,
    RequestId,
    WeightsEdited,
)
from app.modules.mcp.domain.access import Caller

PeerKey = Annotated[
    str,
    Field(
        min_length=1, max_length=100, description="The peer set's key, from get_benchmark_overview"
    ),
]

_READ = ToolAnnotations(read_only_hint=True, open_world_hint=False)
_EDIT = ToolAnnotations(
    read_only_hint=False, destructive_hint=True, idempotent_hint=True, open_world_hint=False
)


def _band(band: Band) -> BandOut:
    return BandOut(
        id=band.id,
        label=band.label,
        max_usd=band.max_usd,
        ebitda_adj=band.ebitda_adj,
        rev_emp_mult=band.rev_emp_mult,
        rent_mult=band.rent_mult,
    )


def _metric(metric: Metric) -> MetricOut:
    return MetricOut(key=metric.key, label=metric.label, unit=metric.unit, weight=metric.weight)


def _cut(cut: PeerCut) -> PeerCutOut:
    return PeerCutOut(
        mode=cut.mode,
        key=cut.key,
        label=cut.label,
        sample_size=cut.sample_size,
        multi_site=cut.multi_site,
        b2b=cut.b2b,
        anchors={metric: list(values) for metric, values in cut.anchors.items()},
    )


def _overview(dataset: BenchmarkDataset) -> BenchmarkOverview:
    return BenchmarkOverview(
        dataset_version=dataset.version,
        sme_metrics=[_metric(m) for m in dataset.metrics["sme"].values()],
        tech_metrics=[_metric(m) for m in dataset.metrics["tech"].values()],
        bands=[_band(b) for b in dataset.bands],
        peer_cuts=[
            PeerCutSummary(**_cut(c).model_dump(exclude={"anchors"}))
            for cuts in dataset.cuts.values()
            for c in cuts.values()
        ],
    )


def _anchors(values: AnchorList) -> Anchors:
    p10, p25, p50, p75, p90 = values
    return (p10, p25, p50, p75, p90)


def _editor(caller: Caller) -> str:
    return caller.name or caller.slack_user_id


def register(server: MCPServer, runner: ToolRunner) -> None:
    _register_overview(server, runner)
    _register_get_peer_cut(server, runner)
    _register_edit_peer_cut(server, runner)
    _register_edit_band(server, runner)
    _register_set_weights(server, runner)


def _register_overview(server: MCPServer, runner: ToolRunner) -> None:
    async def get_benchmark_overview() -> BenchmarkOverview:
        async def call(_: Caller) -> BenchmarkOverview:
            return _overview(await load_dataset())

        return await runner.run(
            "get_benchmark_overview", "benchmark.read", call, output=BenchmarkOverview
        )

    server.tool(
        name="get_benchmark_overview",
        title="Benchmark dataset overview",
        description=(
            "The GCC SME Benchmark's peer dataset in brief: the dataset version, the revenue "
            "bands, each metric's weight in the score, and every peer set (sectors in 'sme' "
            "mode, funding stages in 'tech' mode) with its sample size. Use get_peer_cut for a "
            "peer set's anchors."
        ),
        annotations=_READ,
    )(get_benchmark_overview)


def _register_get_peer_cut(server: MCPServer, runner: ToolRunner) -> None:
    async def get_peer_cut(mode: ModeParam, key: PeerKey) -> PeerCutOut:
        async def call(_: Caller) -> PeerCutOut:
            cut = (await load_dataset()).cuts[mode].get(key)
            if cut is None:
                raise UnknownRecordError(f"No {mode} peer cut '{key}'")
            return _cut(cut)

        return await runner.run("get_peer_cut", "benchmark.read", call, output=PeerCutOut)

    server.tool(
        name="get_peer_cut",
        title="Get a benchmark peer set",
        description=(
            "One peer set with its percentile anchors for every metric, as "
            "[p10, p25, p50, p75, p90].\n"
            'Example: {"mode": "sme", "key": "restaurant"}'
        ),
        annotations=_READ,
    )(get_peer_cut)


def _register_edit_peer_cut(server: MCPServer, runner: ToolRunner) -> None:
    async def edit_benchmark_peer_cut(
        mode: ModeParam,
        key: PeerKey,
        request_id: RequestId,
        sample_size: Annotated[
            int | None, Field(ge=0, description="Companies in the sample")
        ] = None,
        multi_site: bool | None = None,
        b2b: bool | None = None,
        anchors: Annotated[
            dict[str, AnchorList] | None,
            Field(description="Metric key to new [p10..p90]; metrics not sent are unchanged"),
        ] = None,
    ) -> PeerCutEdited:
        edit = PeerCutEdit(
            sample_size=sample_size,
            multi_site=multi_site,
            b2b=b2b,
            anchors=None if anchors is None else {m: _anchors(v) for m, v in anchors.items()},
        )

        async def call(caller: Caller) -> PeerCutEdited:
            edited = await edit_peer_cut(mode, key, edit, edited_by=_editor(caller))
            return PeerCutEdited(peer_cut=_cut(edited.value), dataset_version=edited.version)

        return await runner.run(
            "edit_benchmark_peer_cut",
            "benchmark.write",
            call,
            output=PeerCutEdited,
            request_id=request_id,
            request_args=f"{mode}|{key}|{edit!r}",
        )

    server.tool(
        name="edit_benchmark_peer_cut",
        title="Edit a benchmark peer set",
        description=(
            "Change a peer set's sample size, its multi_site or b2b flags, or its percentile "
            "anchors. Only what is sent changes. It is saved straight away and changes what "
            "visitors are scored against on the public benchmark. Anchors must rise from p10 "
            "to p90. Look the current values up with get_peer_cut first.\n"
            'Example: {"mode": "sme", "key": "restaurant", "anchors": {"gm": [57, 62, 67, 71, '
            '75]}, "request_id": "6f1c..."}'
        ),
        annotations=_EDIT,
    )(edit_benchmark_peer_cut)


def _register_edit_band(server: MCPServer, runner: ToolRunner) -> None:
    async def edit_revenue_band(
        band_id: Annotated[
            str, Field(min_length=1, description="A band id from get_benchmark_overview")
        ],
        request_id: RequestId,
        label: Annotated[str | None, Field(min_length=1, max_length=100)] = None,
        max_usd: Annotated[
            float | None, Field(gt=0, description="New revenue ceiling in USD")
        ] = None,
        ebitda_adj: float | None = None,
        rev_emp_mult: Annotated[float | None, Field(gt=0)] = None,
        rent_mult: Annotated[float | None, Field(gt=0)] = None,
    ) -> BandsEdited:
        edit = BandEdit(
            label=label,
            max_usd=max_usd,
            ebitda_adj=ebitda_adj,
            rev_emp_mult=rev_emp_mult,
            rent_mult=rent_mult,
        )

        async def call(caller: Caller) -> BandsEdited:
            edited = await edit_band(band_id, edit, edited_by=_editor(caller))
            return BandsEdited(
                bands=[_band(b) for b in edited.value], dataset_version=edited.version
            )

        return await runner.run(
            "edit_revenue_band",
            "benchmark.write",
            call,
            output=BandsEdited,
            request_id=request_id,
            request_args=f"{band_id}|{edit!r}",
        )

    server.tool(
        name="edit_revenue_band",
        title="Edit a benchmark revenue band",
        description=(
            "Change a revenue band's label, revenue ceiling or the three factors that shift a "
            "sector's anchors for that band. Only what is sent changes. Saved straight away. "
            "Ceilings must keep rising from the smallest band up, and the top band stays "
            "open-ended.\n"
            'Example: {"band_id": "micro", "ebitda_adj": -2.5, "request_id": "6f1c..."}'
        ),
        annotations=_EDIT,
    )(edit_revenue_band)


def _register_set_weights(server: MCPServer, runner: ToolRunner) -> None:
    async def set_metric_weights(
        mode: ModeParam,
        weights: Annotated[
            dict[str, int], Field(description="Every metric key of the mode to its new weight")
        ],
        request_id: RequestId,
    ) -> WeightsEdited:
        async def call(caller: Caller) -> WeightsEdited:
            edited = await set_weights(mode, weights, edited_by=_editor(caller))
            return WeightsEdited(
                mode=mode, weights=dict(_ordered(edited.value)), dataset_version=edited.version
            )

        return await runner.run(
            "set_metric_weights",
            "benchmark.write",
            call,
            output=WeightsEdited,
            request_id=request_id,
            request_args=f"{mode}|{sorted(weights.items())}",
        )

    server.tool(
        name="set_metric_weights",
        title="Set benchmark metric weights",
        description=(
            "Set how much each metric counts towards a mode's score. Send a weight for every "
            "metric of the mode (see get_benchmark_overview); they must add up to 100. Saved "
            "straight away and changes every visitor's score.\n"
            'Example: {"mode": "tech", "weights": {"growth": 30, "capEff": 20, "revScale": 15, '
            '"gm": 10, "recur": 15, "conc": 10}, "request_id": "6f1c..."}'
        ),
        annotations=_EDIT,
    )(set_metric_weights)


def _ordered(weights: Mapping[str, int]) -> list[tuple[str, int]]:
    return sorted(weights.items())
