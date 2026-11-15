# WusoolScribe meeting notes

How notes typed during a meeting are stored on the Mac, sent to the Toolkit
server and filed in Attio. See [WusoolScribe](scribe.md) for the push flow
and interfaces.

## Storage and sync

Notes typed while recording go to `notes.draft.json` in the recording
folder, because the meeting has no ID until it is saved. Saving the meeting
moves the draft into the local `meeting_notes` table. That covers the normal
stop and the crash recovery path.

The floating notepad is the shared overlay panel, so it floats over
full-screen meeting apps and is kept out of screen shares. Only one of the
notepad and the main window edits the notes at a time.

The first push sends the notes as `user_notes` (markdown, at most 50,000
characters). The server stores them in `meetings.user_notes` and appends
them to the CRM note, in Attio and in `notes.content`, under an
**Advisor notes** heading. `meetings.summary` stays the summary alone.

Later edits to a pushed meeting go to `PUT …/user-notes` a few seconds after
typing stops. The 60-second
background sync retries any that failed. A 404 or 422 stops the retries
until the next edit. The app refuses to save notes over the limit, so they
can't block a push.
