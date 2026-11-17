# Deal rollup

How the interactions engine keeps five fields current on each Deal in Attio. See [Interactions engine](interactions.md) for the rest of the engine. It has been on in production since 17 November.

## What it writes

For each Deal: last interaction, next interaction, last subject, last owner, and connection strength. Nothing else on the Deal is touched. All Deals are included, whatever their stage.

## How it is worked out

A Deal has a seller, always an Organization, and a buyer, which is a Person or an Organization. The engine takes the emails and meetings with both sides together and counts any that involve both once. It then summarizes them as it does for any record.

- Last and next interaction come from either side.
- The subject and owner come from the latest interaction.
- Strength is the strongest relationship across both sides. It has no score of its own.
- A Deal with no recent interactions fades to Very weak and loses its next date.
- If the buyer or seller was last led by a mailbox the engine doesn't read, the Deal's strength is left alone.

## Settings

`INTERACTIONS_DEAL_ROLLUP_MODE` is `off` by default, and `dry_run` logs counts only. It runs inside the Attio write step, so `INTERACTIONS_ATTIO_WRITE_MODE` must be on too. `INTERACTIONS_DEAL_ROLLUP_MAX_PER_ROUND` caps the Deals written per round.

Run the seed first. Until it has, the rollup writes nothing. The steps are in the Google access runbook, `docs/runbooks/google-delegation.md`.
