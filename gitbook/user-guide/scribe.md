# WusoolScribe

WusoolScribe is a Mac app that records and transcribes meetings on your
computer and can generate an editable summary. You can send a finished
meeting to Attio as a note.

Audio and transcription stay on your Mac. A cloud summary provider receives
transcript text only when you choose one. Sending a meeting to Attio sends
the transcript and summary, never the audio.

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

1. Select the microphone and system-audio devices.
2. Optionally name the meeting, then press **Record**.
3. Check that transcript lines appear while people speak.
4. Pause when needed, then press **Stop**.

**Expected result:** the meeting opens as soon as it is saved, so you can
review and edit it straight away. While recording, the menu-bar icon shows a
red dot, or an amber dot when paused.

When a meeting app call ends, a pill counts down 15 seconds with **Keep**
and **Stop now**. To turn this off, use **Settings → Recordings →
Auto-stop When Meeting Ends**.

If only your voice is captured, or no speech appears, see
[Troubleshooting](troubleshooting.md).

## Edit a transcript

Fix the transcript before you summarize or send it:

- Tick lines (Shift-click for a range), then delete, merge, or split them.
- Right-click a line to delete everything before it.
- Use **Find & replace** (Cmd+F) to fix a misheard name everywhere.
- Undo and redo with Cmd+Z and Cmd+Shift+Z.

Deleted lines are not sent to Summarize.

## Summarize a meeting

Generate a summary with the provider chosen in **Settings**: Ollama (runs on
your Mac), Claude, Groq, OpenRouter, OpenAI, or a custom OpenAI-compatible
service. Cloud providers receive the transcript text under their own
data-handling terms.

Treat every summary as a draft. Check names, figures, decisions, and actions
before sharing or sending it.

## Import or enhance existing audio

**Import & Enhance is a beta feature.** Choose **Import**, select an audio
file, and Scribe transcribes it on your Mac. For an existing meeting,
**Enhance** re-transcribes it with another model or language. Keep the
original audio until you have checked the result.

## Send a meeting to Attio

1. Open the meeting and review its transcript and summary.
2. If it concerns a company, search for and select that organization.
3. Press **Push**.

**Expected result:** the meeting shows a processing status, then a completed
status once the note reaches Attio. With an organization selected, the note
links to its buyer or seller record; otherwise it becomes a general note.

You can close the app while processing continues. Don't push again just
because it takes a while. If it fails, see
[Troubleshooting](troubleshooting.md).

## Organize and delete meetings

- Meetings are grouped in folders, with the most recently active first. A
  meeting inside a folder has a back button to that folder's list.
- To delete meetings, select one or more in a folder and delete them. To
  delete a whole folder and every meeting in it, hover over the folder in
  the sidebar and click its delete button.
- When deleting, you can also remove the meetings from the server and Attio.
  If that removal fails, your meetings are kept on your Mac.
- Drag the sidebar's right edge to make it wider.

Follow your organization's retention rules when deleting or sharing meeting
material.

## Send feedback

Click the bug icon at the top of the sidebar, choose a category, and describe
what happened. The form needs **Scribe Push** set up first.

## Updates

Scribe updates itself and offers new versions in a dialog. Use the menu-bar
**Check for Updates** to look now, or **View Changelog** to see what changed.
The full history is in the [Scribe changelog](../release-notes/scribe-changelog.md).
