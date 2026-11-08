const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/** Readable default, e.g. "Meeting · 7 Nov, 18:22". Mirrors `default_meeting_title` in meeting_title.rs. */
export function defaultMeetingTitle(at: Date = new Date()): string {
  const pad = (n: number) => String(n).padStart(2, '0');
  return `Meeting · ${at.getDate()} ${MONTHS[at.getMonth()]}, ${pad(at.getHours())}:${pad(at.getMinutes())}`;
}
