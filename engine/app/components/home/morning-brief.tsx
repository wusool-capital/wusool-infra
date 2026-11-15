import type { Brief } from "../../demo/types";
import { formatTime } from "../../lib/format";

export function MorningBrief({ brief }: { brief: Brief }) {
  return (
    <section className="card home__desktop-only" aria-labelledby="brief-title">
      <div className="card__head">
        <h2 id="brief-title" className="section-title">Morning brief</h2>
        <span className="badge">AI draft</span>
        <span className="card__meta">Sent to Slack at {formatTime(brief.sentAt)}</span>
      </div>
      <ul className="brief-list">
        {brief.bullets.map((bullet) => (
          <li key={bullet}>{bullet}</li>
        ))}
      </ul>
    </section>
  );
}
