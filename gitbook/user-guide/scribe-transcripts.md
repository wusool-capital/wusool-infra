# Work with Scribe transcripts

After a meeting, Scribe shows who said each line. You can name speakers, fix
lines, proofread, and re-transcribe before you summarize or send the meeting.
See [WusoolScribe](scribe.md) to record and send meetings.

## See who said what

Scribe labels each speaker's turn in the transcript:

- **Your lines** come from your microphone and show your name. Set it under
  **Settings → General → Speakers → Your name**.
- **Other people** show as **Others** while you record. When you stop,
  Scribe separates their voices on your Mac into **Speaker 1**, **Speaker 2**,
  and so on, unless you've turned that off.
- **Turn off automatic separation.** **Separate Speakers Automatically**
  under **Settings → General → Speakers** is on by default. Turn it off to
  separate only when you press **Separate Speakers** in a meeting. While
  separation runs, the meeting shows **Separating speakers…** with an
  estimated time left, even if you open it partway through.
- **Same person, two voices.** Scribe sometimes splits one person into two
  voices. Give the second one the same name: names already in the meeting
  say **Combines lines**, and Scribe warns you before it saves. Both voices
  become one row, and both voice samples go to that person, so Scribe
  recognises them better. Combined the wrong person? Press **Undo** within
  10 seconds. After that, move their lines back with **Change Speaker**.
- **Faster separation.** **Faster Speaker Separation (CoreML)** is on by
  default: about 40 seconds for a one-hour meeting, using up to 2.7 GB of
  memory. Scribe offers to download its models (about 300 MB) the first time
  you press **Separate Speakers**.
- **Slower separation.** **Use Slower Model** in that prompt turns CoreML
  off and separates straight away. It takes about four minutes for a
  one-hour meeting, after a one-time 32 MB download. You can change this
  any time under **Settings → General → Speakers**.
- **Name everyone in one place.** Above the transcript, **Who Spoke?**
  lists every separated voice, most talk time first, with one of their
  lines. Press ▶ to hear the quoted line, then type a name. It saves when
  you press Enter, which moves to the next person, or click away. All their
  lines in that meeting are renamed, and Scribe recognises their voice in
  later meetings. Click a quoted line to
  jump to it in the transcript.
- **Check automatic names.** A voice Scribe recognised on its own says
  **recognised by voice**: press **Confirm** if that's right, or **Change**.
- **Confirm a likely match.** When a voice sounds close to someone you've
  named before, Scribe asks "Sounds like Faisal?". Press **Yes** to name
  them, or **No** to type a different name.
- Click a speaker's name on any line to rename them.
- **Fix a wrong speaker.** Right-click a line, or a selection of lines, and
  choose **Change Speaker**. Pick another voice, yourself, or **New
  Speaker** for someone Scribe didn't separate, then name them.
- **Start over.** **Separate Again** in **Who Spoke?** separates the meeting
  from scratch, after asking first. It replaces that meeting's names and moved
  lines; people Scribe already knows are recognised again. Use it if you combined two different people.

Voice fingerprints are stored only on your Mac. To make Scribe forget
someone, delete them under **Settings → General → Speakers**.

If separation failed, for example because you were offline, press
**Separate Speakers** above the transcript to try again.

Speakers are separated for meetings recorded with **Auto-save** on, because
Scribe needs the meeting audio on its own. In imported audio, every voice
becomes a speaker to name, including yours. Enhancing a meeting keeps its
speakers. Without headphones, your microphone also picks up the meeting audio,
and Scribe ignores that echo.

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
- Accept or dismiss each fix, or press **Next Fix** to jump to the next.
  **Accept All** and **Dismiss All** handle them all; if any fixes change a
  name, Accept All lists them first. Cmd+Z undoes Accept All in one step.
- Proofread sends the transcript text, speaker names and meeting title to the
  Toolkit server, and nothing is stored there. If part of a long meeting
  can't be checked, Scribe says how many lines were missed and offers
  **Try Again**.
- Proofread already knows common deal, finance and GCC terms. Add your own
  client names and project code names in **Settings → General → Proofread**.
- Undo and redo with Cmd+Z and Cmd+Shift+Z.

Deleted lines are not sent to Summarize. Filler words such as "um" stay as
recorded, and Summarize receives them. Remove them with Proofread or Find &
Replace.

## Import or enhance existing audio

**Import & Enhance is a beta feature.** Choose **Import**, select an audio
file, and Scribe transcribes it on your Mac. For an existing meeting,
**Enhance** re-transcribes it with another model or language. Keep the
original audio until you have checked the result.
