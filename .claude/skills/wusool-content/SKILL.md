---
name: wusool-content
description: Create and publish a Wusool report or Insights article in Sanity, or check whether a piece is blog-worthy. Use when asked to publish, create, add or upload a report or an insight (article, playbook, case study, press) to Sanity or the Wusool site, or whether an article is worth publishing.
---

# Wusool content: reports and insights to Sanity

Turns an attached file or pasted text into a report or Insights article in the Wusool
Reports & Insights Sanity project (`itidwo8t`, dataset `production`). Claude writes a
draft and publishes only when the person approves. They never need to open the Studio.

Made for Claude chat; also works in Cowork and Claude Code. Every file named below sits
in this skill's folder.

## How to talk to the person

They're Wusool staff, not developers. Keep messages plain, and as short as the content
allows.

- **Never drop something important to stay short.** When the input calls for it (many
  problems, a detailed question, a real trade-off), give the full answer. Cut filler,
  not substance.
- **Lead with the answer or the decision you need.** Group questions only where the
  steps below say to.
- **Show only what needs a decision or went wrong.** Passed checks get one line ("All
  checks passed."). Full details go in `checks.md`, not the chat.
- **Use the Studio's labels**, such as "SEO title" or "web address (slug)", never field
  names like `seoTitle` or `bodyFormat`.
- **No jargon.** Never say Portable Text, GROQ, perspective, draft id, `drafts.`, asset
  reference, render, sync, schema or a tool's name. Say "the draft", "the article",
  "the site", "uploaded".
- **No preamble or recap.** Don't announce what you're about to do or repeat what they
  said. Short sentences, no filler.

These rules cover messages only. When calling tools, use the field names, ids and
queries in these files exactly.

## Step 0: setup check

Stop at the first check that fails and help the person fix it.

1. **Sanity connector.** Call its **whoami** tool, then **list projects**. If either
   fails, or `itidwo8t` isn't listed, tell the person:
   > Add Sanity as a custom connector (`https://mcp.sanity.io`) in Claude's settings,
   > or ask your Claude org owner to add it for everyone. Sign in with the Sanity account
   > that can open Wusool Reports & Insights, then start a new chat.

   Refer to connector tools by what they do: name prefixes differ between apps.
2. **Code tool.** Checks and uploads run in Claude's code tool. If it's off, ask them to
   turn on **Code execution and file creation** in Claude's settings (Capabilities), or
   ask their org owner.
3. **Webflow connector (optional).** Without it, the Webflow address and duplicate
   checks can't run; say so in one line when one is skipped.

Uploads also need the code tool to reach `mcp.sanity.io`, checked at the first upload
(see **Upload a file** in `reference.md`).

## Required steps

Do all of these, in order, every run, even when the request says "create it" or "stop
at the draft". A request to create a draft is not approval to skip them.

1. Step 0 setup check. Say which Sanity account is signed in, in one line.
2. Ask the Step 1 questions you don't have answers to. Always ask question 3 for an
   insight.
3. For an insight: run `blog-worthiness.md` and show the verdict first. On **Revise** or
   **Don't publish**, stop and ask whether to go ahead.
4. Ask for the **staff fields** (see `reference.md`) in one message: the short table,
   then "Still blank: … Leave these blank?". Wait for an explicit OK. Never invent a
   value or write placeholder content.
5. Only then upload files and create the draft.
6. Report briefly: what was created, the link, fields left blank, and anything that
   went wrong.
7. Publish only after the person says "publish" for this document.

## Step 1: ask

Ask these together, in one message:

1. Report or insight?
2. The content: attach the file, or paste the text.
3. For an insight only: "Does this article promote a report?" If yes, ask for the
   report's web address, or offer to create the report first.

## Step 2: working files

Keep the run's files in the code tool, in `wusool-content/<YYYY-MM-DD>-<slug>/`: the input
(`source.md`, `source.html` or `report.html`), `fields.json` with the fields you'll send,
and `checks.md` with every check and its result. At the end, offer `fields.json` and
`checks.md` as downloads.

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
