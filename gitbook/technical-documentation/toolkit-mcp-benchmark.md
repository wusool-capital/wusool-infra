# Benchmark tools in the Wusool MCP

## What it does

Advisors can read and edit the GCC SME Benchmark's peer dataset from Claude, through the [Wusool MCP](toolkit-mcp.md). The tools run in the `mcp` module. The tables belong to the `benchmark_data` module, described in [GCC SME Benchmark](lead-tools-benchmark.md). Sign-in, the call wrapper and the hourly limit work as they do for the CRM tools.

## Tools

| Tool | Does | Saves |
| --- | --- | --- |
| `get_benchmark_overview` | Revenue bands, metric weights, and every peer set with its sample size. Every row shows who last changed it and when | Read only |
| `get_peer_cut` | One peer set with its percentile anchors, and who last changed it | Read only |
| `edit_benchmark_peer_cut` | Change a peer set's sample size, flags or anchors. Only the fields sent change | Straight away |
| `edit_revenue_band` | Change a revenue band's label, ceiling or adjustment factors | Straight away |
| `set_metric_weights` | Set every metric's weight for a mode. They must add up to 100 | Straight away |

Like the CRM tools, none of them deletes, sends, spends provider credits or shows fees.

## Edit rules

The tools change what visitors to the public benchmark are scored against, as soon as they are saved. Each edit is checked first. Anchors must rise from p10 to p90. Band ceilings must keep rising, and only the top band is open-ended. Weights must add up to 100. A refused edit saves nothing.

For anchors, a call sends either a metric's five numbers or only the percentiles to change, such as `{"p50": 67}`. The rest keep their value, and the merged result must still rise from p10 to p90.

Each changed row stores the editor's Slack user id, their name and the time. The tools show the name, with the id beside it. Old values are not kept yet, so Claude reads a row first and tells the person what it held and who last changed it. The tools' own descriptions say so.

## Activity log

- A benchmark edit leaves one `benchmark.peer_cut_edited` or `benchmark.rule_edited` activity per changed row, naming the fields that changed.
- Every call also leaves the usual `mcp.tool_called` activity, as described in [Wusool MCP](toolkit-mcp.md).
- The edit descriptions list the valid metric keys for each mode.

## Limits

- The tools use the same `crm` token scope as the CRM tools, so one connection covers both.
- They declare `benchmark.read` and `benchmark.write`. Every active member passes in v1.
- Adding or removing sectors and stages isn't offered.
