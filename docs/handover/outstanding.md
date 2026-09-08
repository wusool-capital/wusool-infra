# Outstanding items

| Area | Item |
| --- | --- |
| Schema | Confirm production has fully applied the latest database migrations. |
| CRM data | Finish the remaining data-migration scope (investor/lender records, scorecards, and a final owner/advisor backfill) and complete the Attio ↔ database reconciliation audit. |
| n8n | Update the production re-provisioning procedure to match the current infrastructure template, so it no longer risks reverting live configuration fixes if it's ever re-run. |
| Monitoring | Add an automatic failure notification for the nightly Attio → database sync job — today a failure is only visible by checking the job's run history. |

These are tracked delivery items, not defects in what's already live — see
[Delivered components](README.md#delivered-components) for what's confirmed
working today.
