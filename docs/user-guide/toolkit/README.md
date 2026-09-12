# Wusool Toolkit — Getting Started

The Wusool Toolkit is a Slack bot for the deal team. It has nine slash
commands for finding buyer–seller matches, researching missing details, and
keeping buyer and seller profiles up to date.

Everything happens inside Slack — there is no separate website or login. The
bot reads and writes the same customer data the team uses in Attio and in the
Wusool database. Changes you make with `/edit-*` and `/add-*` appear in Attio
first, then in the database a moment later.

## Commands at a glance

| Command | What it does |
| --- | --- |
| [`/find-match <buyer name>`](find-match.md) | Finds and scores the sellers that best fit a buyer, and posts a ranked shortlist. |
| [`/edit-seller <name>`](edit-profile.md) | Edit an existing seller's profile (and, optionally, its organization's details). |
| [`/edit-buyer <name>`](edit-profile.md) | Edit an existing buyer's profile (and, optionally, its organization's details). |
| [`/add-seller <organization name>`](add-buyer-seller.md) | Register a new seller, attaching it to an existing organization or creating a new one. |
| [`/add-buyer <organization name>`](add-buyer-seller.md) | Register a new buyer, attaching it to an existing organization or creating a new one. |
| [`/enrich-seller <name>`](enrich.md) | Research a seller from public sources and propose values for whatever fields are empty. |
| [`/enrich-buyer <name>`](enrich.md) | Same, for a buyer. |
| `/toolkit-status` | Shows the bot's uptime, database connectivity, and whether it's writing to Attio in test or production mode. |
| `/toolkit-help` | Lists every command and how to use it, right in Slack. |

Type the command in any channel or direct message where the bot is present.
Replies are only visible to you.

Each command's own page below includes a worked example — a real command,
what the bot posts back, and what happens next.

## Before you start

- Anyone in the workspace can run these commands — see
  [Rules and limitations](rules-and-limits.md).
- If you run into a problem, see [Getting help](../getting-help.md).
