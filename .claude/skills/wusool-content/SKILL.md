---
name: wusool-content
description: Create and publish a Wusool report or Insights article in Sanity, or check whether a piece is blog-worthy. Use when asked to publish, create, add or upload a report or an insight (article, playbook, case study, press) to Sanity or the Wusool site, or whether an article is worth publishing.
---

# Wusool content: reports and insights to Sanity

Turns a file or pasted text into a report or Insights article in the Wusool Reports &
Insights Sanity project (`itidwo8t`, dataset `production`), after checking it against what
the site can actually render. Claude writes a draft, and publishes it only when the person
approves. The person never needs to open the Studio.

Every file named below sits next to this one, in this skill's folder.

## Step 0: setup check

Run these checks in order, every time. Stop at the first one that fails and help the
person fix it.

1. **Sanity MCP (reads and publishing).** Call its **whoami** tool, then **list projects**.
   If either is missing or fails, or `itidwo8t` isn't listed, tell the person:
   > Run `claude mcp add Sanity -t http https://mcp.sanity.io --scope user`, restart
   > Claude Code, run `/mcp`, pick **Sanity**, and sign in with the Sanity account that
   > has access to the Wusool Reports & Insights project.

   Say which account is signed in. Refer to MCP tools by what they do, not by a prefixed
   name: prefixes differ between installs.
2. **Node.js (for the Sanity CLI, which does the writes).** `node --version` must print
   v20 or later. If not, ask the person to install Node.js LTS from nodejs.org.
3. **Sanity CLI login.** Run this read-only check:

   ```bash
   npx -y sanity@6.19.0 documents query 'count(*[_type == "report"])' -p itidwo8t -d production
   ```

   It should print a number. If it reports a login or permission error, ask the person
   to type `! npx -y sanity@6.19.0 login` and sign in with the same Sanity account.
4. **Permission rules (once per person).** Check them:

   ```bash
   node -e 'const fs=require("fs"),p=process.argv[1];const s=fs.existsSync(p)?JSON.parse(fs.readFileSync(p)):{};const have=new Set(s.permissions?.allow??[]);const need=["Bash(npx -y sanity@6.19.0 documents create *)","Bash(npx -y sanity@6.19.0 assets upload *)","mcp__Sanity__publish_documents"].filter(r=>!have.has(r));console.log(need.length?"missing: "+need.join(" | "):"ok")' ~/.claude/settings.json
   ```

   If it prints `missing`, explain: Claude Code blocks writes to the live Sanity dataset
   unless these three rules allow them. They cover only creating drafts, uploading
   images, and publishing (which this skill still does only on approval). Ask whether to
   add them to `~/.claude/settings.json`. Only on a clear yes, run:

   ```bash
   node -e 'const fs=require("fs"),p=process.argv[1];const s=fs.existsSync(p)?JSON.parse(fs.readFileSync(p)):{};if(fs.existsSync(p))fs.copyFileSync(p,p+".bak");s.permissions??={};s.permissions.allow=[...new Set([...(s.permissions.allow??[]),"Bash(npx -y sanity@6.19.0 documents create *)","Bash(npx -y sanity@6.19.0 assets upload *)","mcp__Sanity__publish_documents"])];fs.writeFileSync(p,JSON.stringify(s,null,2)+"\n")' ~/.claude/settings.json
   ```

   It keeps every existing setting and saves a backup as `settings.json.bak`. If the
   person's Sanity MCP tools carry a different prefix than `mcp__Sanity__`, use their
   publish tool's full name instead. Without the rules, the skill still works, but
   Claude Code asks before each write.

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

- Publish without the person's approval for that document, or unpublish or delete
  anything.
- Write `renderedHtml`, `renderedPreviewEnd` or `renderedFrom`.
- Touch the report `6ea065ae-fae1-4c7e-a3ec-6d67304ccc17` or its draft.
