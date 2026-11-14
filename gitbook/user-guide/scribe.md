# WusoolScribe

WusoolScribe is a Mac app that records and transcribes meetings on your
computer. You can send a finished meeting to Attio as a note with a summary.

Audio and transcription stay on your Mac. Sending a meeting to Attio sends
the transcript and its speaker names, never the audio.

## Install and set up

WusoolScribe runs on Apple-silicon Macs (M1 or later).

1. Download the `.dmg` file from the link your team supplied and save it to
   your **Downloads** folder.
2. Double-click the `.dmg` file and drag **WusoolScribe** to
   **Applications**.
3. Open **Terminal** and run:

   ```bash
   xattr -cr /Applications/WusoolScribe.app
   ```

   macOS blocks apps downloaded outside the App Store until this is run.
4. Open WusoolScribe and allow microphone and screen-recording access when
   asked.
5. Go to **Settings → Scribe Push**, enter the server URL and API key your
   Wusool administrator gave you, then click **Save**.

**Expected result:** Settings shows "Connection successful", and the first
launch downloads a local transcription model. Scribe also starts in the menu
bar each time you log in; turn this off with **Settings → Recordings → Open
at Login**.

After each update, macOS may ask for microphone and screen-recording access
again. Allow it, or recordings will be silent.

## Record a meeting

1. Check the microphone and system-audio devices. Set the defaults under
   **Settings → Recordings → Default Audio Devices**.
2. Optionally name the meeting, then press **Start Recording** on the home
   screen. The home screen shows which microphone and system audio will be
   used.
3. Check that the level meter beside the timer moves when you speak, and that
   transcript lines appear while people speak. A flat meter means the
   microphone hears nothing.
4. Pause when needed, then press **Stop**.

**Expected result:** the meeting opens as soon as it is saved, so you can
review and edit it straight away. While recording, the menu-bar icon shows a
red dot, or an amber dot when paused.

When a meeting app call ends, a pill counts down 15 seconds with **Keep**
and **Stop now**. To turn this off, use **Settings → Recordings →
Auto-stop When Meeting Ends**.

If only your voice is captured, or no speech appears, see
[Troubleshooting](troubleshooting.md).

## Take notes during a meeting

While you record, the screen splits into the transcript and your notes. Type
in **Notes** as the meeting goes. Notes save as you type.

- Drag the line between the two sides to give either more room. Double-click
  it to reset the split.
- To take notes over another app, click the notepad button beside **Notes**,
  or choose **Open Notepad** from the menu-bar icon. The notepad stays on top
  of other windows and is hidden from screen shares. Click **Return to app**
  to move your notes back.

**Expected result:** when you stop, your notes open beside the transcript of
the saved meeting. When you push, Scribe sends your notes with the
transcript, and the summary gives weight to what you noted. The Attio note
shows your notes under **Advisor notes**, after the summary. You can keep
editing notes after a push: open the meeting's **Notes** tab, and Scribe
updates the Attio note. Editing notes after a push doesn't rewrite the
summary.

## Work with the transcript

Name speakers, fix lines, proofread, and re-transcribe in
[Work with Scribe transcripts](scribe-transcripts.md).

## Summarize a meeting

Press **Summarize** on the meeting, then **Push**. Scribe sends the
transcript to the Toolkit server, which writes the summary. Scribe doesn't
summarize on your Mac, and Settings has no summary provider to choose.

Treat every summary as a draft. Check names, figures, decisions, and actions
before sharing or sending it.

## Send a meeting to Attio

1. Open the meeting and review its transcript.
2. If it concerns a company, search for and select that organization.
3. Press **Push**.

**Expected result:** the meeting shows a processing status, then a completed
status once the note reaches Attio. With an organization selected, the note
links to its buyer or seller record; otherwise it becomes a general note.
When the summary is ready, Scribe closes the popup and opens the meeting's
**Summary** tab.

The summary that comes back is built to scan. It shows, in this order:

- a gist of 2–3 sentences: where the meeting landed and what it waits on;
- **Next steps**, each starting with the owner's name;
- **Decisions**, when something was agreed;
- **Deal signal** for buyer, seller and investor meetings: momentum, claims to
  verify before relying on them, and risks. Other meetings show **Risks**;
- **Notes**, grouped by topic. A short call gets 1–2 topics; a 90-minute
  meeting gets up to 8.

The Attio note and `summary.md` in the meeting folder follow the same order.
Meetings summarised before version 0.8.2 keep their longer opening.

You can close the app while processing continues. Don't push again just
because it takes a while. If it fails, see
[Troubleshooting](troubleshooting.md).

## Organize and delete meetings

- Meetings are grouped in folders, with the most recently active first. A
  meeting inside a folder has a back button to that folder's list.
- To delete meetings, select one or more in a folder and delete them. To
  delete a whole folder and every meeting in it, hover over the folder in
  the sidebar and click its delete button.
- When deleting a meeting you already sent, you can tick **Also delete from
  Wusool server & Attio**. It is unticked by default. If that removal fails,
  your meetings are kept on your Mac.
- Drag the sidebar's right edge to make it wider.

Follow your organization's retention rules when deleting or sharing meeting
material.

## Send feedback

Click the bug icon at the top of the sidebar, choose a category, and describe
what happened. The form needs **Scribe Push** set up first. If you gave your
name under **Speakers** in Settings, it's already filled in; change or clear it
as you like.

## Updates

Scribe updates itself and offers new versions in a dialog. Use the menu-bar
**Check for Updates** to look now, or **View Changelog** to see what changed.
The full history is in the [Scribe changelog](../release-notes/scribe-changelog.md).
