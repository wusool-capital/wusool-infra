---
name: wusool-content
description: Create a Wusool report or Insights article as a Sanity draft, or check whether a piece is blog-worthy. Use when asked to publish, create, add or upload a report or an insight (article, playbook, case study, press) to Sanity or the Wusool site, or whether an article is worth publishing.
---

# Wusool content: reports and insights to Sanity

Turns a file or pasted text into a **draft** in the Wusool Reports & Insights Studio
(project `itidwo8t`, dataset `production`), after checking it against what the site
can actually render. Never publishes: the person reviews and publishes in the Studio.

Every file named below sits next to this one, in this skill's folder.

## Step 0: check the Sanity MCP

1. Call the Sanity MCP's **whoami** tool, then its **list projects** tool.
2. If either tool is missing or fails, or `itidwo8t` isn't in the list, stop and tell
   the person:
   > Connect the Sanity MCP: run `claude mcp add Sanity -t http https://mcp.sanity.io --scope user`,
   > restart Claude Code, run `/mcp`, pick **Sanity**, and sign in with the
   > Sanity account that has access to the Wusool Reports & Insights project.
3. Say which Sanity account is signed in.

Refer to MCP tools by what they do (create documents, patch documents, query
documents), not by a prefixed tool name: prefixes differ between installs.

## Step 1: ask

Ask these together, in one message:

1. Report or insight?
2. Where's the content: a file path, or pasted text?
3. For an insight only: "Is this insight + report?" (does it promote a report?).
   If yes, ask for the report's slug, or offer to run the report flow first.

## Step 2: working folder

Create `wusool-content/<YYYY-MM-DD>-<slug>/` in the current directory, using today's
date and the proposed slug (rename the folder if the slug changes). Everything this
run produces goes there.

## Step 3: follow the sub-skill

Read `reference.md` first, then read and follow `reports.md` or `insights.md`.
For insight + report, finish the report flow before starting the insight.

If the person only wants to know whether a piece is blog-worthy, skip question 3, then
follow `blog-worthiness.md` alone and stop at its verdict: no draft.

## Never

- Publish, unpublish, or discard anything the person didn't ask you to.
- Write `renderedHtml`, `renderedPreviewEnd` or `renderedFrom`.
- Touch the report `6ea065ae-fae1-4c7e-a3ec-6d67304ccc17` or its draft.
