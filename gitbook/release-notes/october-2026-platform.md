# October 2026: Platform, data, and documentation

Delivery period: 15 September – 10 October 2026.

## CRM data and sync

- **Deletions stay in step.** A record deleted in Attio now disappears from
  the database for all six synced record types, not just two. Deleted deals,
  notes, and buyer and seller profiles used to linger and appear in matching
  and reports. Removals are reversible: a record re-created in Attio comes
  back on its own.
- **Safer nightly sync.** The nightly sync checks its totals after handling
  deletions, and notes can be reconciled safely. Two gaps in synced fields,
  organization activity and deal time-in-stage, were filled.
- **Buyers by sector.** The CRM was restructured so each buyer holds one
  profile per sector, migrated from existing data. Buyer geography was split
  into target regions and target countries. Every production buyer was
  converted.
- **Each seller's own sector.** Sellers now carry their sector on their own
  profile.
- **Lead source detail.** Organizations record which lead tool brought them
  in, in both Attio and the database.
- **Discovery memory.** Organizations remember the Google Maps place they came
  from, so a company can't be created twice under a slightly different name.
- **Faster matching.** New database indexes let matching filter by sector
  and geography in the database.
- **Migration tools.** The CRM migration scripts can insert new records
  without rewriting existing ones, and ticket sizes import correctly.
- Meeting notes now attach to the whole organization rather than one
  arbitrary profile.

## Detected and fixed

On 28 September, a sync running against an older deployment switched off
639 of 913 buyer profiles. It treated each organization as having a single
profile. No data was deleted: only an "active" flag changed. The flags were
restored the next day with a repair script and the sync was corrected. The
older list-sync script now refuses to touch buyer profiles.

## Infrastructure and operations

- **Website stack.** The server can render complex reports in a headless
  browser, which powers the gated reports.
- **Report security.** A signed Sanity webhook, a code-gated reader flow, and
  per-visitor rate limits.
- **Alerts.** An alarm for failed lead emails, alongside the nightly sync
  alert.
- **Architecture viewer.** The interactive architecture diagram was rebuilt
  with the services added this period: email, the Scribe update feed, Google
  Maps, and the security monitoring.

## Documentation

These docs were reviewed end to end and rebuilt:

- **Fit for each reader.** Every User Guide page was rewritten for
  non-technical staff, then tested with a fresh reader. There is a new
  Glossary and a "Publish in Sanity" guide.
- **Per module and per tool.** The Technical section was split into module
  pages for the Slack bot and per-tool pages for the lead tools. Each was
  checked line by line against the code.
- **Engine deep dives.** New pages explain the discrepancy check and seller
  discovery in depth.
- **Handover-ready operations.** The Operations pages were rewritten with
  the real deploy and rollback steps and a full alarm table. They also cover
  what isn't alarmed, backup coverage, and a current list of open items.
- **New diagrams.** Ten diagrams were redrawn in Wusool's brand colors.
- **Clean-up.** Duplicate pages from an old GitBook export were removed.
- **Quality checks.** Every page passes the automated documentation checks.
