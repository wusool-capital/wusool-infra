// meeting_title.rs
//
// The name a recording gets until someone renames it or the summary supplies a title.

use chrono::{DateTime, TimeZone};
use once_cell::sync::Lazy;
use regex::Regex;

/// Readable default, e.g. "Meeting · 7 Nov, 18:22". Mirrors `defaultMeetingTitle` in the frontend.
pub fn default_meeting_title<Tz: TimeZone>(at: &DateTime<Tz>) -> String
where
    Tz::Offset: std::fmt::Display,
{
    format!("Meeting · {}", at.format("%-d %b, %H:%M"))
}

// Older builds wrote "Meeting 2026-08-20_17-42-02" (backend) and "Meeting 20_08_26_17_42_02" (frontend).
static DEFAULT_TITLE: Lazy<Regex> = Lazy::new(|| {
    Regex::new(concat!(
        r"^Meeting (?:",
        r"· \d{1,2} (?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec), \d{2}:\d{2}",
        r"|\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}",
        r"|\d{2}_\d{2}_\d{2}_\d{2}_\d{2}_\d{2}",
        r")$"
    ))
    .unwrap()
});

/// True only for an auto-generated name, so a summary title never replaces a name someone chose.
pub fn is_default_meeting_title(title: &str) -> bool {
    DEFAULT_TITLE.is_match(title)
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::{FixedOffset, TimeZone};

    #[test]
    fn default_title_is_readable_and_recognised() {
        let at = FixedOffset::east_opt(0).unwrap().with_ymd_and_hms(2026, 11, 7, 8, 5, 9).unwrap();
        let title = default_meeting_title(&at);
        assert_eq!(title, "Meeting · 7 Nov, 08:05");
        assert!(is_default_meeting_title(&title));
    }

    #[test]
    fn titles_from_older_builds_are_still_recognised() {
        assert!(is_default_meeting_title("Meeting 2026-08-20_17-42-02"));
        assert!(is_default_meeting_title("Meeting 20_08_26_17_42_02"));
    }

    #[test]
    fn real_titles_are_left_alone() {
        assert!(!is_default_meeting_title("Q3 Renewal Call"));
        assert!(!is_default_meeting_title("Meeting notes 2026-08-20"));
        assert!(!is_default_meeting_title("Meeting · 7 Nov, 18:22 with Acme"));
    }
}
