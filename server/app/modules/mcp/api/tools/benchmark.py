"""Read and edit the GCC SME Benchmark's peer dataset: the revenue bands, the
metric weights and each peer set's percentile anchors. Edits change what
visitors are scored against straight away. Every row shows who last changed it,
by name, so read a row before editing it."""

from collections.abc import Mapping
from typing import Annotated

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

from app.modules.activities import ActivitySource
from app.modules.benchmark_data import (
    ANCHOR_ONLY_KEYS,
    METRIC_KEYS,
    Anchors,
    Band,
    BandEdit,
    BenchmarkDataset,
    Editor,
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
    BandList,
    BandOut,
    BenchmarkOverview,
    MetricList,
    MetricOut,
    ModeParam,
    PeerCutOut,
    PeerCutSummary,
    RequestId,
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


def _metric_keys_note() -> str:
    """The valid metric keys per mode, so a caller can name them without a lookup."""
    sme, tech = ", ".join(METRIC_KEYS["sme"]), ", ".join(METRIC_KEYS["tech"])
    return f"Metric keys: sme = {sme}; tech = {tech}."


def _anchor_only_note() -> str:
    return (
        f"Anchors can also be set for {ANCHOR_ONLY_KEYS['sme'][0]} (sme) and "
        f"{ANCHOR_ONLY_KEYS['tech'][0]} (tech, the forward revenue multiple behind a startup's "
        "implied value). They aren't scored and have no weight."
    )


def _band(band: Band) -> BandOut:
    return BandOut(
        code=band.code,
        label=band.label,
        max_usd=band.max_usd,
        ebitda_adj=band.ebitda_adj,
        rev_emp_mult=band.rev_emp_mult,
        rent_mult=band.rent_mult,
        updated_by=band.updated_by,
        updated_at=band.updated_at,
    )


def _metric(metric: Metric) -> MetricOut:
    return MetricOut(
        key=metric.key,
        label=metric.label,
        unit=metric.unit,
        weight=metric.weight,
        updated_by=metric.updated_by,
        updated_at=metric.updated_at,
    )


def _summary(cut: PeerCut) -> PeerCutSummary:
    return PeerCutSummary(
        mode=cut.mode,
        key=cut.key,
        label=cut.label,
        sample_size=cut.sample_size,
        multi_site=cut.multi_site,
        b2b=cut.b2b,
        updated_by=cut.updated_by,
        updated_at=cut.updated_at,
    )


def _cut(cut: PeerCut) -> PeerCutOut:
    return PeerCutOut(
        **_summary(cut).model_dump(),
        anchors={metric: list(values) for metric, values in cut.anchors.items()},
    )


def _overview(dataset: BenchmarkDataset) -> BenchmarkOverview:
    return BenchmarkOverview(
        dataset_updated_at=dataset.updated_at,
        sme_metrics=[_metric(m) for m in dataset.metrics["sme"].values()],
        tech_metrics=[_metric(m) for m in dataset.metrics["tech"].values()],
        bands=[_band(b) for b in dataset.bands],
        peer_cuts=[_summary(c) for cuts in dataset.cuts.values() for c in cuts.values()],
    )


def _anchors(values: AnchorList) -> Anchors:
    p10, p25, p50, p75, p90 = values
    return (p10, p25, p50, p75, p90)


def _editor(caller: Caller) -> Editor:
    return Editor(slack_user_id=caller.slack_user_id, name=caller.name)


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
            "The GCC SME Benchmark's peer dataset in brief: the revenue bands, each metric's "
            "weight in the score, and every peer set (sectors in 'sme' mode, funding stages in "
            "'tech' mode) with its sample size. Every row shows who last changed it, by name, "
            "and when. Use get_peer_cut for a peer set's anchors."
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
            "[p10, p25, p50, p75, p90], and who last changed it and when. Read it before "
            "editing it.\n"
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
    ) -> PeerCutOut:
        edit = PeerCutEdit(
            sample_size=sample_size,
            multi_site=multi_site,
            b2b=b2b,
            anchors=None if anchors is None else {m: _anchors(v) for m, v in anchors.items()},
        )

        async def call(caller: Caller) -> PeerCutOut:
            cut = await edit_peer_cut(
                mode, key, edit, editor=_editor(caller), source=ActivitySource.MCP
            )
            return _cut(cut)

        return await runner.run(
            "edit_benchmark_peer_cut",
            "benchmark.write",
            call,
            output=PeerCutOut,
            request_id=request_id,
            request_args=f"{mode}|{key}|{edit!r}",
        )

    server.tool(
        name="edit_benchmark_peer_cut",
        title="Edit a benchmark peer set",
        description=(
            "Change a peer set's sample size, its multi_site or b2b flags, or its percentile "
            "anchors. Only what is sent changes. It is saved straight away under the "
            "signed-in person's name and changes what visitors are scored against on the "
            "public benchmark. Anchors must rise from p10 to p90. The old values are not kept: "
            "read the peer set with get_peer_cut first, and tell the person what it held and "
            "who last changed it. Required: mode, key and request_id; everything else is "
            "optional and only what you send changes. The peer set's key comes from "
            "get_benchmark_overview. " + _metric_keys_note() + " " + _anchor_only_note() + "\n"
            'Example: {"mode": "sme", "key": "restaurant", "anchors": {"gm": [57, 62, 67, 71, '
            '75]}, "request_id": "6f1c..."}'
        ),
        annotations=_EDIT,
    )(edit_benchmark_peer_cut)


def _register_edit_band(server: MCPServer, runner: ToolRunner) -> None:
    async def edit_revenue_band(
        code: Annotated[
            str, Field(min_length=1, description="A band code from get_benchmark_overview")
        ],
        request_id: RequestId,
        label: Annotated[str | None, Field(min_length=1, max_length=100)] = None,
        max_usd: Annotated[
            float | None, Field(gt=0, description="New revenue ceiling in USD")
        ] = None,
        ebitda_adj: float | None = None,
        rev_emp_mult: Annotated[float | None, Field(gt=0)] = None,
        rent_mult: Annotated[float | None, Field(gt=0)] = None,
    ) -> BandList:
        edit = BandEdit(
            label=label,
            max_usd=max_usd,
            ebitda_adj=ebitda_adj,
            rev_emp_mult=rev_emp_mult,
            rent_mult=rent_mult,
        )

        async def call(caller: Caller) -> BandList:
            bands = await edit_band(code, edit, editor=_editor(caller), source=ActivitySource.MCP)
            return BandList(bands=[_band(b) for b in bands])

        return await runner.run(
            "edit_revenue_band",
            "benchmark.write",
            call,
            output=BandList,
            request_id=request_id,
            request_args=f"{code}|{edit!r}",
        )

    server.tool(
        name="edit_revenue_band",
        title="Edit a benchmark revenue band",
        description=(
            "Change a revenue band's label, revenue ceiling or the three factors that shift a "
            "sector's anchors for that band. Only what is sent changes. Saved straight away "
            "under the signed-in person's name. Ceilings must keep rising from the smallest band "
            "up, and the top band stays open-ended. The old values are not kept: read the band "
            "with get_benchmark_overview first, and tell the person what it held and who last "
            "changed it. Required: code and request_id; the rest is optional and only what you "
            "send changes. Band codes come from get_benchmark_overview.\n"
            'Example: {"code": "micro", "ebitda_adj": -2.5, "request_id": "6f1c..."}'
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
    ) -> MetricList:
        async def call(caller: Caller) -> MetricList:
            metrics = await set_weights(
                mode, weights, editor=_editor(caller), source=ActivitySource.MCP
            )
            return MetricList(mode=mode, metrics=[_metric(m) for m in _by_key(metrics)])

        return await runner.run(
            "set_metric_weights",
            "benchmark.write",
            call,
            output=MetricList,
            request_id=request_id,
            request_args=f"{mode}|{sorted(weights.items())}",
        )

    server.tool(
        name="set_metric_weights",
        title="Set benchmark metric weights",
        description=(
            "Set how much each metric counts towards a mode's score. Send a weight for every "
            "metric of the mode (see get_benchmark_overview); they must add up to 100. Saved "
            "straight away under the signed-in person's name and changes every visitor's score. "
            "The old weights are not kept: read them with get_benchmark_overview first, and tell "
            "the person what they were and who last changed them. Send every metric of the mode "
            "and no others. " + _metric_keys_note() + "\n"
            'Example: {"mode": "tech", "weights": {"growth": 30, "capEff": 20, "revScale": 15, '
            '"gm": 10, "recur": 15, "conc": 10}, "request_id": "6f1c..."}'
        ),
        annotations=_EDIT,
    )(set_metric_weights)


def _by_key(metrics: Mapping[str, Metric]) -> list[Metric]:
    return list(metrics.values())
