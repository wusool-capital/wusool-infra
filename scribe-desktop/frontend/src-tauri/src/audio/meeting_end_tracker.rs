// Pure state machine deciding when a recorded meeting has ended. Kept free of
// CoreAudio/Tauri so the transitions are unit-testable.
#![cfg_attr(not(target_os = "macos"), allow(dead_code))]

#[derive(Debug, PartialEq, Eq)]
pub enum MeetingSignal {
    Idle,
    /// A meeting app was using the mic during this recording and has let go.
    Ended,
    /// A meeting app took the mic again after `Ended`.
    Reacquired,
}

#[derive(Debug)]
pub struct MeetingEndTracker {
    inactive_threshold: u32,
    saw_meeting: bool,
    inactive_polls: u32,
    ended: bool,
}

impl MeetingEndTracker {
    pub fn new(inactive_threshold: u32) -> Self {
        Self {
            inactive_threshold,
            saw_meeting: false,
            inactive_polls: 0,
            ended: false,
        }
    }

    /// Feed one poll of "is any meeting app/browser holding the mic".
    pub fn observe(&mut self, meeting_active: bool) -> MeetingSignal {
        if meeting_active {
            self.saw_meeting = true;
            self.inactive_polls = 0;
            if self.ended {
                self.ended = false;
                return MeetingSignal::Reacquired;
            }
            return MeetingSignal::Idle;
        }

        self.inactive_polls += 1;
        // Only arm after a meeting was seen, so in-person recordings never
        // trigger an auto-stop.
        if self.saw_meeting && !self.ended && self.inactive_polls >= self.inactive_threshold {
            self.ended = true;
            return MeetingSignal::Ended;
        }
        MeetingSignal::Idle
    }

    /// The user chose to keep recording; stay quiet until a meeting app
    /// grabs the mic again.
    pub fn keep_recording(&mut self) {
        self.saw_meeting = false;
        self.inactive_polls = 0;
        self.ended = false;
    }

    pub fn reset(&mut self) {
        self.keep_recording();
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn tracker() -> MeetingEndTracker {
        MeetingEndTracker::new(2)
    }

    #[test]
    fn in_person_recording_never_ends() {
        let mut t = tracker();
        for _ in 0..10 {
            assert_eq!(t.observe(false), MeetingSignal::Idle);
        }
    }

    #[test]
    fn ends_after_threshold_of_inactive_polls() {
        let mut t = tracker();
        assert_eq!(t.observe(true), MeetingSignal::Idle);
        assert_eq!(t.observe(false), MeetingSignal::Idle);
        assert_eq!(t.observe(false), MeetingSignal::Ended);
        assert_eq!(t.observe(false), MeetingSignal::Idle);
    }

    #[test]
    fn single_blip_does_not_end() {
        let mut t = tracker();
        t.observe(true);
        assert_eq!(t.observe(false), MeetingSignal::Idle);
        assert_eq!(t.observe(true), MeetingSignal::Idle);
        assert_eq!(t.observe(false), MeetingSignal::Idle);
    }

    #[test]
    fn reacquired_cancels_and_can_end_again() {
        let mut t = tracker();
        t.observe(true);
        t.observe(false);
        assert_eq!(t.observe(false), MeetingSignal::Ended);
        assert_eq!(t.observe(true), MeetingSignal::Reacquired);
        t.observe(false);
        assert_eq!(t.observe(false), MeetingSignal::Ended);
    }

    #[test]
    fn keep_recording_rearms_only_after_meeting_returns() {
        let mut t = tracker();
        t.observe(true);
        t.observe(false);
        assert_eq!(t.observe(false), MeetingSignal::Ended);
        t.keep_recording();
        for _ in 0..5 {
            assert_eq!(t.observe(false), MeetingSignal::Idle);
        }
        t.observe(true);
        t.observe(false);
        assert_eq!(t.observe(false), MeetingSignal::Ended);
    }
}
