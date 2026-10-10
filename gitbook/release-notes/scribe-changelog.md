# Scribe changelog

What changed in each version of the WusoolScribe desktop app, newest first. Entries for versions before 0.4.10 are summaries.

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
