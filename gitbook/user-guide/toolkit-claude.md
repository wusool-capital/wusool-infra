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
| Show everything about a buyer or seller | Shows every field of the record, for up to 100 at a time |
| List buyers or sellers that fit some criteria | Any field can be a criterion, including computed ones such as benchmark score or last interaction. For example: active Fintech buyers in the GCC with an EBITDA ceiling above $2M. Claude reads the list 50 at a time and keeps going until it has them all. Ranking, such as the top 10 by EBITDA, takes one more step to read the numbers |
| Check a buyer's profile | Shows what's missing or in conflict, as `/check-buyer` does in Slack |
| Add a buyer or seller | Saved at once. If the company already has that record, Claude shows the existing one instead |
| Change some fields of a record | Saved at once. Only the fields you name change |
| Add a list of buyers or sellers | Claude checks the list first and shows how many are new and how many already exist. Nothing is saved until you say go |
| Show how an import is going | Shows how many rows were added, skipped and failed |
| Show the benchmark's peer data | Lists the peer sets, revenue bands and metric weights, or one peer set's numbers |
| Change a benchmark peer set, band or weights | Saved at once, and visitors are scored against the new numbers straight away |

For example: "Which active buyers would write a $5M check in the UAE?" Or: "Add Acme Capital (acme.com) as a Fintech buyer with mandate status Active". Or: "Here are 140 sellers from my research: add the new ones".

## Adding a list

1. Give Claude the list, for example the output of a research skill.
2. Claude checks every row. If any row has a problem, nothing is saved, and Claude lists each problem by row so it can fix them and check again.
3. Claude shows the counts: new rows, and rows already in the CRM (matched by website), which are skipped.
4. Say go. The rows are added in the background. Ask Claude for progress at any time.

## Editing the benchmark

The GCC SME Benchmark on the website scores each visitor against peer sets. You can read and edit those numbers from Claude.

- Ask Claude to show a peer set first, so you see the current numbers.
- A peer set holds five anchors per metric: the 10th, 25th, 50th, 75th and 90th percentile. They must rise in that order. You can change just one, such as the median, and the other four stay.
- Revenue band ceilings must keep rising, and the top band stays open-ended.
- A metric's weights for a mode must add up to 100, so send all of them together.
- Every row shows who last changed it, by name, and when. Claude reads the row first and tells you what it held. Old values aren't kept yet, so a change can't be undone from here.
- If an edit is refused, nothing is saved and Claude explains why.
- You can't add or remove a sector or stage from Claude.

For example: "Show me the restaurant peer set". Then either "Change the restaurant gross margin anchors to 57, 62, 67, 71, 75" or "Set the restaurant gross margin median to 67".

## Good to know

- A company is matched by its website domain, not its name. `shop.acme.com` and `acme.com` are different domains.
- Adding never changes an existing company's details. Edit the record instead.
- The company name, domain and a buyer's target vertical can't be edited from Claude. To cover another vertical, add a new buyer.
- Nothing here deletes records, sends email or shows fees.
- A benchmark edit applies to every visitor from then on. Check the numbers before you say go.
- Every change shows in the record's activity with source `mcp`, and every call you make from Claude is logged against you.
