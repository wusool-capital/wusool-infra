# WusoolScribe

WusoolScribe is a Mac app that records and transcribes meetings on your
computer and can generate an editable summary. You can send a finished
meeting to Attio as a note.

Audio and transcription stay on your Mac. A cloud summary provider receives
transcript text only when you choose one. Sending a meeting to Attio sends
the transcript, its speaker names, and the summary, never the audio.

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

## See who said what

Scribe labels each speaker's turn in the transcript:

- **Your lines** come from your microphone and show your name. Set it under
  **Settings → General → Speakers → Your name**.
- **Other people** show as **Others** while you record. When you stop,
  Scribe separates their voices on your Mac and relabels them **Speaker 1**,
  **Speaker 2**, and so on. On the standard model this takes about four
  minutes for a one-hour meeting, after a one-time 32 MB download.
  **Faster Speaker Separation (CoreML)** is on by default and takes about 40
  seconds, using up to 2.7 GB of memory while it runs. Its models (about
  300 MB) download only when you ask. The first time you press **Separate
  Speakers**, Scribe offers the download. **Use Slower Model** turns it off
  and separates straight away. You can also download them, or turn the setting off, under
  **Settings → General → Speakers**.
- **Name everyone in one place.** Above the transcript, **Who Spoke?**
  lists every separated voice, most talk time first, with one of their
  lines. Press ▶ to hear a few seconds of their voice, type a name and
  press Enter to move on to the next person. Every line they spoke in that
  meeting is renamed, and Scribe recognises their voice in later meetings.
  Click a quoted line to jump to it in the transcript.
- **Confirm a likely match.** When a voice sounds close to someone you've
  named before, Scribe asks "Sounds like Faisal?". Press **Yes** to name
  them, or **No** to type a different name.
- You can still click a speaker's name on any line to rename them.

Voice fingerprints are stored only on your Mac. To make Scribe forget
someone, delete them under **Settings → General → Speakers**.

If speakers were not separated, for example because you were offline, press
**Separate Speakers** above the transcript to try again.

Speakers are only separated for meetings recorded with **Auto-save** on,
because Scribe needs the meeting audio on its own. Imported meetings are not
separated. Enhancing a meeting keeps its speakers. Without headphones, your
microphone also picks up the meeting audio, and Scribe ignores that echo.

## Edit a transcript

Fix the transcript before you summarize or send it:

- Hover over a line to show its tick box, or click its time. Shift-click
  selects a range. Then delete, merge, or split the selected lines.
- Right-click a line to delete everything before it.
- Press **Tidy Lines** to join short fragments from the same speaker into
  full sentences. It never changes a word, and Cmd+Z undoes it.
- Use **Find & Replace** (Cmd+F) to fix a misheard name everywhere.
- Press **Proofread** to get suggested fixes for misheard words, names and
  terms. Each fix shows its type (name, term, number, word or punctuation).
  Accept or dismiss each one, press **Next Fix** to jump to the next, or
  press **Accept All** or **Dismiss All**. Cmd+Z undoes Accept All in one step.
  Scribe sends the transcript text, speaker names and meeting title to the
  Toolkit server for this, and nothing is stored there. If part of a long
  meeting can't be checked, Scribe says how many lines were missed and offers
  **Try Again**.
- Proofread already knows common deal, finance and GCC terms. Add your own
  client names and project code names in **Settings → General → Proofread**.
- Undo and redo with Cmd+Z and Cmd+Shift+Z.

Deleted lines are not sent to Summarize. Filler words such as "um" appear
exactly as recorded, because that is the text Summarize receives. Remove them
with Proofread or Find & Replace.

## Summarize a meeting

Generate a summary with the provider chosen in **Settings**. The built-in
model and Ollama run on your Mac; Claude, Groq, OpenRouter, OpenAI, and a
custom OpenAI-compatible service are online. Cloud providers receive the transcript text under their own
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
