# Use Wusool from Claude

The Wusool connector lets you find, add and edit buyers and sellers from a Claude conversation, and add a whole researched list at once. Changes go to Attio and the Wusool database under your own name, with the same duplicate checks as the Slack commands.

## Before you start

- A Claude organization owner adds the Wusool connector once for everyone.
- You need an active account in the Wusool Slack workspace. Guest accounts can't connect.

## Connect once

1. In Claude, open **Settings → Connectors** and click **Connect** next to Wusool.
2. Sign in with Slack when asked, and allow access.
3. You're back in Claude, connected. Claude keeps you signed in. If you leave the Slack workspace, the connection stops working within an hour.

## What you can ask

| Ask Claude to… | What happens |
| --- | --- |
| Find a buyer or seller by name or website | Lists matching records |
| Add a buyer or seller | Saved at once. If the company already has that record, Claude shows the existing one instead |
| Change some fields of a record | Saved at once. Only the fields you name change |
| Add a list of buyers or sellers | Claude checks the list first and shows how many are new and how many already exist. Nothing is saved until you say go |
| Show how an import is going | Shows how many rows were added, skipped and failed |

For example: "Add Acme Capital (acme.com) as a Fintech buyer with mandate status Active". Or: "Here are 140 sellers from my research: add the new ones".

## Adding a list

1. Give Claude the list, for example the output of a research skill.
2. Claude checks every row. If any row has a problem, nothing is saved, and Claude lists each problem by row so it can fix them and check again.
3. Claude shows the counts: new rows, and rows already in the CRM (matched by website), which are skipped.
4. Say go. The rows are added in the background. Ask Claude for progress at any time.

## Good to know

- A company is matched by its website domain, not its name. `shop.acme.com` and `acme.com` are different domains.
- Adding never changes an existing company's details. Edit the record instead.
- The company name, domain and a buyer's target vertical can't be edited from Claude. To cover another vertical, add a new buyer.
- Nothing here deletes records, sends email or shows fees.
- Every change shows in the record's activity with source `mcp` and your name.
