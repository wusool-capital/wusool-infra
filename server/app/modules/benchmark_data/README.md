# benchmark_data

The GCC SME Benchmark's peer dataset in Postgres: revenue bands, metric weights,
peer cuts (sectors in `sme` mode, funding stages in `tech` mode) and their
percentile anchors. The benchmark tool reads it to score visitors. Advisors read
and edit it from Claude through the `mcp` module.

The scoring formula is not here. The percentile engine, score bands and report
copy stay in `lead_magnets`. This module owns only the numbers they read.

## Tables

Two tables, current values only (`app/models/benchmark_data.py`):

- **`benchmark_peer_cuts`**: one row per peer cut. `anchors` is JSONB,
  `{metric: [p10, p25, p50, p75, p90]}`, parsed through the `AnchorSet` model in
  `persistence/repository.py` on every read and write.
- **`benchmark_rules`**: revenue bands (`kind = 'band'`) and metric weights
  (`kind = 'metric'`). Each kind fills its own columns; a CHECK enforces it.

Both have a uuid `id`, `created_at`/`created_by` and `updated_at`/`updated_by`.
`updated_by` is the editor's Slack user id (`seed` for the loaded dataset), which is
unique and can later be matched to a user. `updated_by_name` is the name they had
when they edited, so a row reads as a person. The `users` table holds Attio workspace
members and has no Slack link yet, so there is no foreign key to it.

There is no history table. An edit overwrites the old value; the audit tables
will keep history. Until then the activity names which fields changed.

## What can change

| Edit | Rule |
| -- | -- |
| A peer cut's sample size, `multi_site`, `b2b`, or any anchor row (all five percentiles, or just the ones named) | Anchors rise from p10 to p90 after merging. Sample size isn't negative |
| A revenue band's label, ceiling or three factors | Ceilings keep rising, only the top band is open-ended, multipliers above zero |
| A mode's metric weights | Every metric of the mode, adding up to 100 |

Every number must be finite, and a band's ceiling above zero. An edit locks the rows it reads until it commits, so two edits can't overwrite each other. An edit that changes nothing writes nothing. Adding or removing a peer cut isn't
offered: each sector is also mapped to a CRM sector option in
`lead_magnets/domain/shared/sector_mapping.py`, and `lead_magnets/api/schemas.py`
validates `peer_key` against `benchmark_dataset.py`, which still lists every key.

## Activities

Each changed row leaves one `activities` event in the same transaction:
`benchmark.peer_cut_edited` (subject `BenchmarkPeerCut`) or `benchmark.rule_edited`
(subject `BenchmarkRule`), actor the Slack user, source `mcp`, payload the names of
the changed fields (`anchors.<metric>` per changed metric).

## Structure

```
benchmark_data/
  config.py          # BenchmarkDataSettings: DATABASE_URL
  bootstrap.py       # the public functions: load_dataset, edit_peer_cut, edit_band, set_weights
  domain/dataset.py  # frozen dataclasses (Band, Metric, PeerCut, Editor) and the edit rules
  application/       # service.py applies an edit and records it; ports/repository.py is the storage Protocol
  persistence/       # repository.py: the Postgres adapter, mapping rows to domain values
```

## Seed

Migration `c2f9a6e1b583` creates the tables and loads the dataset as it stood in
`lead_magnets/domain/benchmark/benchmark_dataset.py` on 2026-08-17, attributed to
`seed`. An integration test checks the tables against that file value by value, so
a score doesn't move when the tool starts reading them. Migration `d8a3f5c17e64`
lets `activities` take the benchmark and MCP call subjects.
