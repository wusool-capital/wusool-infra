# Attio CRM

Attio is Wusool Capital's business-facing CRM and the normal place to view
organization, person, buyer, seller, deal, ownership, and relationship
information.

## Find a record

1. Sign in to the Wusool Attio workspace using your administrator's invite.
2. Use global search for the organization or person's name.
3. Open the organization, then follow its linked buyer, seller, person, deal,
   or mandate records as needed.
4. Check similar names and domains before creating anything new.

**Expected result:** the record shows its current attributes, related records,
notes, and activities according to your permissions.

| Information | Where to look |
| --- | --- |
| Toolkit additions and edits | Organization and linked buyer or seller |
| Scribe meeting output | Note on the selected organization/role, or a general note without an organization |
| Valuation, readiness, or benchmark submission | Organization and seller context |
| Buyer Network application | Organization and buyer context |

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
value; no second organization was created. If the update is absent, wait for
the normal synchronization delay, then report the record URL, field, and edit
time. Do not create a replacement record to work around a delayed update.

## Edit safely

- Update the existing organization when it is the same entity; avoid creating
  near-duplicates.
- Keep domains and identifying details accurate because integrations use them
  to match records.
- Direct Attio changes are copied to the Wusool database by a real-time
  webhook and scheduled resynchronization. A brief delay does not necessarily
  mean the change failed.
- Use Toolkit for guided buyer/seller forms and Attio for fields or
  relationships the Slack forms do not expose.

**Expected result:** a saved change appears in Attio immediately and later in
connected systems. If it remains missing after the normal sync delay, report
the record URL, field, and approximate edit time.

{% hint style="warning" %}
Do not merge, delete, or restructure CRM records unless the CRM owner confirms
the procedure. Toolkit does not provide role-removal commands.
{% endhint %}
