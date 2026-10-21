# Website analytics

## What it does

The tools report to PostHog so the team can see where visitors start, finish
or leave a tool, and how many book a call. Reports use the same project. See
[Gated reports](lead-tools-reports.md) for the report events.

## Events

- **Browser events** are opened, started, step completed, completed and
  abandoned, plus Book a Call clicks inside a tool. They are sent only after
  the visitor accepts tracking. They carry the tool, the step, the language and
  a random submission id, and never a form value. Session recording is off.
- **Server events** count every lead (`lead_submitted`) and every click on an
  email's Book a Call button. They are sent whether or not the visitor accepted
  tracking.

## Banner choices

Each click on the consent banner's Accept or Decline is counted, so the team
can see the acceptance rate. The count carries no visitor id and sets no
cookie, so it never identifies the person who clicked. Visitors who never click
aren't counted.

## Who is named

- A visitor who declined is counted but never identified. The event has no
  email and no name.
- A visitor who accepted has their name, email and company linked to their
  earlier page views. The Persons list then shows what each lead did.
- A lead's first-touch campaign tags (the `utm_` values in the link they
  arrived by) are saved with the lead.

## Email button

The Book a Call button in each email goes through the Toolkit. The Toolkit
redirects to the right calendar and counts the click. The tool picks the
calendar, never the link.

## Counting caveats

- Some mail scanners open every link in an email, so email clicks can be
  overcounted for recipients on Microsoft 365 and similar systems.
- Visitors who decline tracking or block scripts send no browser events. The
  server still counts their leads and email clicks, so the funnel's early steps
  undercount them.

## Endpoints

| Endpoint | Purpose |
| --- | --- |
| `GET /analytics/config` | The public PostHog key and host a page loads PostHog with, after the visitor accepts tracking |
| `GET /analytics/consent` | Counts a consent banner click anonymously |
| `GET /go/book-call/{tool}` | Redirects to the tool's calendar and counts the click |

## Code

`server/app/modules/lead_magnets`: `static/shared/analytics.js`,
`api/analytics.py`, and `providers/posthog`.
