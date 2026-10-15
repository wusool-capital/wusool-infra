---
name: wusool-content
description: Create and publish a Wusool report or Insights article in Sanity, or check whether a piece is blog-worthy. Use when asked to publish, create, add or upload a report or an insight (article, playbook, case study, press) to Sanity or the Wusool site, or whether an article is worth publishing.
---

# Wusool content: reports and insights to Sanity

Turns an attached file or pasted text into a report or Insights article in the Wusool
Reports & Insights Sanity project (`itidwo8t`, dataset `production`), after checking it
against what the site can actually render. Claude writes a draft, and publishes it only
when the person approves. The person never needs to open the Studio.

Made for Claude chat; it also works in Cowork and Claude Code. Every file named below
sits next to this one, in this skill's folder.

## Step 0: setup check

Stop at the first check that fails and help the person fix it.

1. **Sanity connector.** Call its **whoami** tool, then **list projects**. If either is
   missing or fails, or `itidwo8t` isn't listed, tell the person:
   > Add Sanity as a custom connector (`https://mcp.sanity.io`) in Claude's settings,
   > or ask your Claude org owner to add it for everyone. Sign in with the Sanity account that has access
   > to the Wusool Reports & Insights project, then start a new chat.

   Say which account is signed in. Refer to connector tools by what they do, not by a
   prefixed name: prefixes differ between apps.
2. **Code tool.** Checks and file uploads run in Claude's code tool. If it isn't
   available, ask the person to turn on **Code execution and file creation** in
   Claude's settings (Capabilities), or ask their org owner.
3. **Webflow connector (optional).** Without it, the Webflow slug and duplicate checks
   can't run; say so whenever one is skipped.

File uploads also need the code tool to reach `mcp.sanity.io`. That's checked at the
first upload (see **Upload a file** in `reference.md`).

## Required steps

Do all of these, in order, every run, even when the request already says "create it" or
"stop at the draft". A request to create a draft is not approval to skip them.

1. Step 0 setup check, and say which Sanity account is signed in.
2. Ask the Step 1 questions you don't already have answers to. Always ask question 3
   for an insight.
3. For an insight: run `blog-worthiness.md` and show the verdict before anything else.
   On **Revise** or **Don't publish**, stop and ask whether to go ahead.
4. Ask for the **staff fields** (see `reference.md`): every non-content field, in one
   table with your suggestions and what blank means. Then list the ones still blank,
   ask "Leave these blank?", and wait for an explicit OK. Never invent a value or write
   placeholder content.
5. Only then upload files and create the draft.
6. Report what was written and every staff field left blank.
7. Publish only after the person says "publish" for this document.

## Step 1: ask

Ask these together, in one message:

1. Report or insight?
2. The content: attach the file, or paste the text.
3. For an insight only: "Is this insight + report?" (does it promote a report?).
   If yes, ask for the report's slug, or offer to run the report flow first.

## Step 2: working files

Keep the run's files in the code tool, in `wusool-content/<YYYY-MM-DD>-<slug>/`: the input (`source.md`, `source.html` or
`report.html`), `fields.json` with the fields you'll send, and `checks.md` with every
check and its result. At the end, offer `fields.json` and `checks.md` as downloads.

## Step 3: follow the sub-skill

Read `reference.md` first, then read and follow `reports.md` or `insights.md`.
For insight + report, finish the report flow before starting the insight.

If the person only wants to know whether a piece is blog-worthy, skip question 3, then
follow `blog-worthiness.md` alone and stop at its verdict: no draft.

## Never

- Publish without the person's approval for that document, or unpublish or delete
  anything.
- Paste a large file into the conversation or into a tool call: upload it.
- Write `renderedHtml`, `renderedPreviewEnd` or `renderedFrom`.
- Touch the report `6ea065ae-fae1-4c7e-a3ec-6d67304ccc17` or its draft.
