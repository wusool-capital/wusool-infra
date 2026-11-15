# benchmark_data

The GCC SME Benchmark's peer dataset in Postgres: revenue bands, metric weights,
peer cuts (sectors in `sme` mode, funding stages in `tech` mode) and their
percentile anchors. The benchmark tool reads it to score visitors. Advisors read
and edit it from Claude through the `mcp` module.

The scoring formula is not here. The percentile engine, score bands and report
copy stay in `lead_magnets`. This module owns only the numbers they read.

## What can change

| Edit | Rule |
| -- | -- |
| A peer cut's sample size, `multi_site`, `b2b`, or any anchor row | Anchors rise from p10 to p90. Sample size isn't negative |
| A revenue band's label, ceiling or three factors | Ceilings keep rising, only the top band is open-ended, multipliers above zero |
| A mode's metric weights | Every metric of the mode, adding up to 100 |

Adding or removing a peer cut isn't offered. Each sector is also mapped to a CRM
sector option in `lead_magnets/domain/shared/sector_mapping.py`, so a new one is a
code change. `api/schemas.py` in `lead_magnets` validates `peer_key` against
`benchmark_dataset.py`, which still lists every key.

Every edit runs in one transaction, stores `updated_by` and `updated_at` on the
rows it touched, and bumps `benchmark_dataset_version`.

## Structure

```
benchmark_data/
  config.py          # BenchmarkDataSettings: DATABASE_URL
  bootstrap.py       # the public functions: load_dataset, edit_peer_cut, edit_band, set_weights
  domain/dataset.py  # frozen dataclasses (BenchmarkDataset, Band, Metric, PeerCut) and the edit rules
  application/       # service.py applies an edit; ports/repository.py is the storage Protocol
  persistence/       # repository.py: the Postgres adapter, mapping rows to domain values
```

ORM models are in `app/models/benchmark_data.py`. Tables: `benchmark_bands`,
`benchmark_metrics`, `benchmark_peer_cuts`, `benchmark_anchors`,
`benchmark_dataset_version`.

## Seed

Migration `c2f9a6e1b583` creates the tables and loads the dataset as it stood in
`lead_magnets/domain/benchmark/benchmark_dataset.py` on 2026-08-17 (version 1),
attributed to `seed`. An integration test checks the table against that file
value by value, so a score doesn't move when the tool starts reading the table.
