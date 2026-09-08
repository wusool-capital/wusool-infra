# Pushing meetings to the CRM

WusoolScribe can send a meeting's summary to the Wusool server, which
generates a structured note and files it against the right organization in
Attio.

## One-time setup: Push Destination

In **Settings → Push Destination**, enter:

- **Server URL** — the Wusool server's address (ask your engineering
  contact for this).
- **API Key** — a shared key your engineering contact provides.

WusoolScribe checks the URL and key before saving, so you'll know
immediately if something's wrong.

Each install also has an **Install ID**, generated automatically and shown
on this same screen — quote it if you ever need support.

## Pushing a meeting

1. Open a completed meeting with a summary.
2. If the meeting is about a specific company, tag it with that
   organization (search by name).
3. Press **Push**.

The server generates a structured note from the summary and files it in
Attio, linked to that organization's buyer or seller record when one exists.
A meeting with no organization is still filed as a general note.

Pushing can take a little while to finish generating the note on the
server — you don't need to wait with the app open; the meeting's status
updates automatically once it's done.
