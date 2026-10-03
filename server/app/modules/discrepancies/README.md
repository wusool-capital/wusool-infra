# discrepancies

Checks a buyer role for two things before a match runs: does the
advisor's own typed context conflict with what's on file (vertical,
geography, ticket band, EBITDA), and is anything required missing from the
buyer's profile. Deterministic rules decide; the one Bedrock call only
turns a flagged result into a sentence.

Promoted out of `matching_engine` (AZM-92/WP3) so this check can also run
on its own, via `/check-buyer <name>`, not just inside `/find-match`. See
`docs/internal/dev/MODULAR_MONOLITH_GUIDE.md` for the layering rules every
module here follows.

## Structure

```
domain/          vocabulary, BuyerCriteria/DiscrepancyReport, the pure rules
application/     orchestration (check.py) + ports (criteria_reader, phraser)
providers/       the one Bedrock phrasing call
api/             Slack command (/check-buyer) and the composition root
```

No `persistence/` — this module reads buyer criteria through
`BuyerCriteriaReaderPort`, implemented by `matching_engine` (it already owns
buyer search/lookup) and wired at startup by `server/main.py`. Same shape
`discovery.SellerDraftPort` uses for its own reverse hand-off.

## Public contract

`BuyerCriteria`, `DiscrepancyReport`, `DiscrepancyCheckResult`,
`check_buyer_discrepancies` (called directly by `matching_engine`, which
already has the buyer's data and maps it to `BuyerCriteria` itself),
`build_discrepancy_blocks`, `BuyerCriteriaReaderPort`,
`configure_criteria_reader_port` — see `__init__.py`.

## Setup

Needs `SLACK_BOT_TOKEN`/`SLACK_SIGNING_SECRET` (standalone run only —
`server/main.py` shares one Bolt app across every module) and AWS Bedrock
credentials. See `.env.example`'s `discrepancies only` section.

## Testing

```
uv run pytest app/modules/discrepancies/tests
```
