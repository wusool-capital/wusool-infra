# Scribe changelog

What changed in each version of the WusoolScribe desktop app, newest first. Entries for versions before 0.4.10 are summaries.

## 0.8.5

### What's new

* **Import Audio** now separates speakers too. Every voice in the file, including yours, appears in **Who Spoke?** to name.
* **Separate Speakers Automatically** in **Settings → General → Speakers** can be turned off, so speakers are separated only when you press **Separate Speakers**.
* Giving two voices in **Who Spoke?** the same name merges them into one row, for when Scribe splits one person in two. Scribe warns you before it saves, and **Undo** separates them again.
* Separating speakers shows an estimated time left and a progress bar. The estimate gets more accurate as Scribe learns how fast your Mac separates.
* **Change Speaker** fixes lines given to the wrong person. Right-click a line, or a selection of lines, and pick a speaker, yourself, or **New Speaker** for someone Scribe didn't separate.

### Fixed

* When a summary is ready, Scribe opens the meeting's **Summary** tab instead of leaving the transcript and its buttons behind the popup.
* **Summarize** no longer runs off the edge of the toolbar in a narrow window.
* A name typed in **Who Spoke?** saves when you click away, not only when you press Enter.
* ▶ in **Who Spoke?** plays the voice again. It plays each voice's longest line, so you hear more of the person.
* ▶ in **Who Spoke?** still plays after your headphones disconnect, instead of going silent.
* Speaker separation can no longer run for ages and use up your Mac's memory. A run that takes far longer than expected is stopped and retried on the slower, lighter model, and quitting Scribe now always stops it too.
* A meeting opened while its speakers are still being separated shows **Separating speakers…** instead of the **Separate Speakers** button.

## 0.8.4

### Fixed

* **Proofread** no longer renames people to words from your vocabulary or to the meeting's speakers. Every fix must sound like what was said, and a bad change no longer takes a good fix on the same line with it.
* **Accept All** lists any fixes that change a name before applying them.
* Scribe auto-names a voice only when it clearly matches one person. Voices it recognised on its own say **recognised by voice**, with **Confirm** and **Change**.

## 0.8.3

### What's new

* **Faster Speaker Separation (CoreML)** is now on by default. Its models (about 300 MB) download only when you ask. The first time you press **Separate Speakers**, Scribe offers the download with a progress bar. **Use Slower Model** instead turns CoreML off and separates straight away, with no download. Separation that runs on its own after a recording uses the standard model until then.

### Changed

* Summaries are shorter and easier to scan. A 2–3 sentence gist comes first, then next steps with the owner's name, decisions, and notes by topic. Buyer, seller and investor meetings also show a deal signal: momentum, claims to verify and risks. Notes grow with the meeting, from 1–2 topics for a short call to up to 8 for a 90-minute meeting. Older summaries keep their longer opening.
* **Proofread** catches more misheard names and terms. It knows common deal, finance and GCC terms, plus the meeting's speakers and title. Add your own words in **Settings → General → Proofread**. Each fix marks only the words it changes and shows its type. **Next Fix** steps through them, and **Accept All** confirms how many it applied. When part of a long meeting couldn't be checked, Scribe keeps saying so and offers **Try Again**.
* **Send feedback** fills in the name you gave under **Speakers** in Settings, so you don't have to type it again.

## 0.8.2

### What's new

* **Who Spoke?** above the transcript lists every separated voice with how long they spoke and one of their lines. Play a few seconds of a voice, type a name and press Enter to move on to the next person, with no scrolling.
* When a voice sounds close to someone you've named before, Scribe asks "Sounds like Faisal?" so you can confirm with one click.
* The meeting header shows how many speakers are still to name.
* Turning on **Faster Speaker Separation (CoreML)** downloads its models straight away with a progress bar. Turning it off asks whether to keep the models, so switching back on later needs no download.

### Changed

* Dropdowns and menus clearly highlight the option under the pointer, in light and dark mode.
* **Recording Settings** on the home screen opens the Recording tab of Settings directly.
* Changing your microphone or system audio in Settings shows straight away on the home screen.
* Select All (⌘A) only selects text inside text fields. You can still drag to select text in summaries, transcripts, and meeting titles and headings.
* Long meeting titles in a folder end with "…" instead of pushing the date off the edge of the window.
* New meetings are named like "Meeting · 7 Nov, 18:22" instead of a file-style timestamp. Your own titles are never replaced by the summary's title.
* Dialogs look sharp instead of slightly blurry, with a lighter background behind them. **Rename Meeting** selects the current name so you can type over it.

### Fixed

* The CoreML download bar fills as the download progresses and shows the real size, instead of sitting at 100%.
* After **Tidy Lines**, transcript lines no longer overlap until you resize the window.
* The sidebar keeps the width you set instead of stretching to fit long meeting titles. It can be at most 420 px wide, and double-clicking its edge resets it.
* Meeting titles in the sidebar have more room. The edit and delete buttons replace the date only while you point at a meeting.
* The transcript toolbar fits beside a wide sidebar: its buttons switch to icons when space runs out, and **Summarize** is never cut off.
* Settings fit beside a wide sidebar: text wraps, switches stay visible, and the tabs tighten up instead of running off the edge.

## 0.8.1

### What's new

* **Tidy Lines** joins short fragments from the same speaker into full sentences, in one step you can undo.

### Changed

* A sent meeting's summary opens with its action items and decisions, and the page header shows when it was sent to Attio. Copy sits beside the tabs.
* While recording, one bar at the bottom shows the status, timer, a live microphone level, and Pause and Stop. The level meter now reflects what the microphone actually hears.
* The home screen shows which microphone and system audio a recording will use, with one **Start Recording** button.
* **Test Mic** in Settings shows the real level of the selected microphone. It used to show a simulated level.
* Live transcripts break into full sentences instead of short fragments, which also makes them more accurate. Lines appear a second or two after people stop speaking.

## 0.8.0

### What's new

* Transcripts show who said each line. Your lines carry your name, set under **Settings → General → Speakers**. After a meeting, Scribe separates the other voices on your Mac into Speaker 1, Speaker 2 and so on.
* Click a speaker's name to say who they are. Scribe renames everything they said in that meeting and recognises their voice in later meetings. Voice fingerprints stay on your Mac.
* **Faster Speaker Separation (CoreML)** in Settings separates voices about six times faster, using more memory while it runs.
* **Proofread** suggests fixes for misheard words. Accept or dismiss each one, or all at once.
* Meetings pushed to Attio carry each speaker's name instead of "Participant".

### Changed

* The meeting page shows the meeting's name and date at the top. Long lines are no longer cut off when the window is narrow, and tick boxes appear only when you hover or start selecting.
* Settings are grouped into clearer sections, and the auto-stop description no longer runs under its switch.
* Transcripts show filler words such as "um" as recorded, matching the text that Summarize and Attio receive.

## 0.7.7

### What's new

* Hover over a folder in the sidebar to show a delete button. It deletes the folder and every meeting in it, after you confirm.
* Drag the sidebar's right edge to make it wider, up to 70% of the window. Scribe remembers the width.

## 0.7.6

### What's new

* The menu-bar icon shows a red dot while Scribe is recording and an amber dot while recording is paused. You can tell at a glance that a meeting is being captured.

## 0.7.5

### Changed

* Stopping a recording opens its meeting as soon as it is saved, so you can review, edit or summarize the transcript right away. This applies to the Stop button, the menu-bar "Stop Recording" item, the countdown pill's "Stop now" and auto-stop when a meeting ends.
* Scribe comes to the front when the meeting opens, even if you switched to another app while it finished transcribing.

## 0.7.4

### What's new

* **Open at Login** setting under Recording, on by default. Scribe starts in the menu bar when you log in, without opening its window. macOS shows a "Background Items Added" notice the first time.
* A back button on meetings that belong to a folder returns you to that folder's meeting list.
* The sidebar orders folders by recent activity.

### Fixed

* "Processing recording" and "Finalizing transcription" now look the same after you stop a meeting.
* Sidebar folder names show on one line and scroll sideways on hover instead of wrapping.
* The sidebar stops highlighting the last opened meeting once you leave it.
* The folder page header keeps its meeting and selected counts on one line.

## 0.6.0

### What's new

* More transcript editing before you summarize: select lines with checkboxes (Shift-click for a range), then delete, merge or split them. Right-click a line to delete everything before it.
* Find & replace fixes a misheard name across the whole transcript.
* Undo and redo (Cmd+Z, Cmd+Shift+Z) cover every change. Deleted lines are not sent to Summarize.
* A "Proofread" button for AI spelling suggestions shows as "Coming soon".

### Fixed

* Clickable controls show the hand cursor, including menu and dropdown items.
* Pressing X on "Start recording?" or "Keep" on the meeting-ended countdown no longer brings Scribe forward.
* Start-recording buttons react instantly and show a spinner while capture starts.

## 0.5.0

### What's new

* Scribe stops recording automatically when a meeting ends. A pill counts down 15 seconds, with "Keep" and "Stop now" buttons. It never triggers when no meeting app was seen. Turn it off in Settings.
* Refreshed meeting popups share one card design with the WusoolScribe logo. "Record" and "Stop now" open the home page. Changed in 0.7.5.

### Fixed

* The popup close button works on the first click and is visible without hovering.
* Popups no longer show an oversized background rectangle behind the card.
* Folder pages no longer carry selections over from another folder.

## 0.4.10

### What's new

* Select several meetings in a folder and delete them together.
* Optionally remove the meetings from the server and Attio too. The recording folder is removed from your Mac.

### Fixed

* If the server or Attio removal fails, your local meetings are kept.
* Select all only covers the meetings your search shows.

## 0.4.9

### What's new

* In-app feedback: a bug icon opens a form that sends your report to the team.
* New Inter font to match the Wusool Capital website.

### Fixed

* The feedback dialog is centered.

## 0.4.8

### Fixed

* Scrollable areas no longer show a duplicate scrollbar.

## 0.4.7

### Fixed

* Push-destination save errors no longer show the server address or raw network errors.
* Scrolling works on every list and panel, and the toast styling now appears in installed builds.
* Removed the extra in-page Back buttons.

## 0.4.6

### Fixed

* The window title bar now follows the app's dark-mode setting.

## 0.4.5

### What's new

* A "Connection successful" message appears when your push destination checks out.

### Fixed

* A wrong server URL that still responds is now rejected before it is saved.
* Release notes in the update dialog keep their line breaks.

## 0.4.4

### What's new

* Settings checks your server URL and API key when you press Save, so a bad setting is caught immediately.
* Summaries appear on their own once ready. No more manual "Check" clicks.
* The menu-bar icon uses its own artwork, and the About logo has rounded corners.

### Fixed

* A meeting's time is its real recording time, even when you summarize it later.
* Meeting lists are sorted latest first.
* The sidebar scrollbar follows dark mode.

## 0.4.3

### Fixed

* The sidebar footer shows the real app version.
* Removed outdated "delivered to Slack" wording from the push-destination settings.
* The record button no longer flashes off-center when you return to Home.

## 0.4.2

### Fixed

* After an update, Scribe comes to the front instead of opening behind other windows.
* The "Update available" toast matches the app's theme.
* The update dialog now shows release notes.

## 0.4.1

### What's new

* Scribe updates itself. A dialog offers new versions, and the menu-bar "Check for Updates" item looks for one on demand.
