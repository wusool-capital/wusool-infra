# Wusool Toolkit — Getting Started

The Wusool Toolkit is a Slack bot for the deal team. It has five slash
commands for finding buyer–seller matches and for keeping buyer and seller
profiles up to date.

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

Type the command in any channel or direct message where the bot is present.
Replies are only visible to you.

![The Toolkit bot's slash commands, as they appear in Slack's command autocomplete.](../../images/toolkit-slash-commands.png)

## Before you start

- Anyone in the workspace can run these commands — see
  [Rules and limitations](rules-and-limits.md).
- If you run into a problem, see [Getting help](../getting-help.md).
