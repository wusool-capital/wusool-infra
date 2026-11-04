# Find matches on the web

The same flow runs in a browser at `/app` on the Toolkit host, for example
`https://tools.wusoolcapital.com/app` in production.

1. Choose **Sign in with Slack** and allow it in Slack the first time. You
   stay signed in for 30 days after your last visit.
2. Type the buyer's name and pick the record with the mouse or the arrow keys
   and Enter.
3. Add your note about the search, if any, then **Check profile**. Missing or
   conflicting details show here, as in Slack. **Run match** starts the run.
   After fixing the buyer with `/edit-buyer`, choose **Check again**.
4. The steps bar under the title shows where the run is. Matching usually
   takes under a minute, and the page updates by itself.
5. The run page opens on the first seller still to review. The strip at the
   top counts the sellers considered, those that passed the filters, the
   shortlist and your approvals. The ranked list is on the left. The selected
   seller's score, reasons, pitch and risks are on the right, with
   **Approve** and **Reject** at the bottom. Move through the list with the
   up and down arrow keys. After each decision the next seller waiting for
   review opens.

   A CRM seller also shows Slack's criteria breakdown. A seller found outside
   the CRM shows what Google Maps and basic enrichment found: country,
   sector, website, employees, founding year and any revenue estimate.
   **Buyer and mandate** shows the thesis, ideal target and hard requirements
   the run matched against.
6. If Attio already has a deal for the pair, choose **Use this deal** (up to
   three, each linked to Attio) or **Create a new deal**. Approving a seller
   found outside the CRM also posts full research on it to the Slack review
   channel, as approving it in Slack does.
7. If no seller scores 50 or more, the search outside the CRM starts by
   itself. Otherwise **Outside the CRM** offers **Find more sellers anyway**,
   as Slack's **Find more sellers** does. New sellers from Google Maps join
   the list under **Found outside the CRM** for review. Each run searches
   once.
8. **Download CSV**, next to the title, saves the shortlist with every
   decision so far. Choose its columns under **Settings → CSV export**. The
   default **Business** preset keeps rank, seller, score, decision, why it
   matches, pitch and risks. **Everything** adds the rest.

The home page lists your recent runs with how many sellers each still has to
review. **Settings** explains what each decision writes, picks the CSV columns for
this browser, and lets you clear the recent-runs list.

The web version differs from Slack in a few ways:

- You sign in with your Slack account, so runs and decisions are recorded under
  your name, as in Slack. You stay signed in for 30 days after your last visit.
- **Recent runs** on the home page lists runs started on that device only.
- To fill in missing buyer details, use `/edit-buyer` in Slack, then check
  again. The other commands are Slack-only for now.
- If the Toolkit restarts during a run, the page says the run never finished.
  Start a new one.
