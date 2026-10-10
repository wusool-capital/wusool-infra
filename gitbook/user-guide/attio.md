# Attio CRM

Attio is Wusool Capital's business-facing CRM and the normal place to view
organization, person, buyer, seller, deal, ownership, and relationship
information.

## Find a record

1. Sign in to the Wusool Attio workspace using your administrator's invite.
2. Use global search for the organization or person's name.
3. Open the organization, then follow its linked buyer, seller, person, or
   deal records as needed.
4. Check similar names and domains before creating anything new.

**Expected result:** the record shows its current attributes, related records,
notes, and activities according to your permissions.

| Information | Where to look |
| --- | --- |
| Toolkit additions and edits | Organization and linked buyer or seller |
| Scribe meeting output | Note on the selected organization/role, or a general note without an organization |
| Approved Toolkit match | A Qualified Buy-side deal linked to the buyer and seller |
| Valuation, Readiness, Benchmark, or Get Started submission | Organization and seller context |
| Buyer Network application | Organization, with one buyer role per sector chosen |
| Gated report reader | A person, plus an organization if they gave one |

The exact lists and views depend on workspace configuration and permissions.
Search the underlying record if a saved view does not show an expected lead.

## Example: verify a Toolkit update

Suppose Toolkit confirms that **Example Manufacturing** was updated after an
operator changed its seller revenue.

1. Search Attio for `Example Manufacturing`.
2. Open the organization whose domain matches the company.
3. Follow the linked seller record and confirm the new revenue.
4. Check the activity time against the Toolkit confirmation.

**Expected result:** the existing organization and seller show the updated
value; no second organization was created. Don't create a replacement record
to work around a missing update; see below.

## Edit safely

- Update the existing organization when it is the same entity; avoid creating
  near-duplicates.
- Keep domains and identifying details accurate because integrations use them
  to match records.
- Changes made directly in Attio reach the other tools within a few minutes.
- Use Toolkit for guided buyer/seller forms and Attio for fields or
  relationships the Slack forms do not expose.

If a change is still missing elsewhere after a few minutes, report the record
URL, field, and approximate edit time.

{% hint style="warning" %}
Leave merging, deleting, and removing roles to the CRM owner. Toolkit has no
commands for these.
{% endhint %}
