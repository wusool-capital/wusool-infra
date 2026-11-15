import { useState } from "react";
import type { AgendaItem, Deal, Meeting, Person } from "../../demo/types";
import { byId } from "../../lib/by-id";
import { dayKey, formatDate, formatLongDate, formatTime } from "../../lib/format";
import { EmptyState } from "../ui/empty-state";

type AgendaProps = { items: AgendaItem[]; deals: Deal[]; people: Person[]; now: string };

function itemDay(item: AgendaItem) {
  return item.kind === "meeting" ? dayKey(item.start) : item.date;
}

export function Agenda({ items, deals, people, now }: AgendaProps) {
  const today = dayKey(now);
  const days = [...new Set(items.map(itemDay))].sort();

  return (
    <section className="card home__desktop-only" aria-labelledby="agenda-title">
      <div className="card__head">
        <h2 id="agenda-title" className="section-title">Today and this week</h2>
      </div>
      {items.length === 0 && <EmptyState>No meetings or deadlines this week.</EmptyState>}
      {days.map((day) => (
        <div className="agenda-day" key={day}>
          <h3 className="group-label">{day === today ? "Today" : formatLongDate(day).replace(/ \d{4}$/, "")}</h3>
          <ul className="agenda-list">
            {items
              .filter((item) => itemDay(item) === day)
              .map((item) =>
                item.kind === "meeting" ? (
                  <MeetingRow key={item.id} meeting={item} deals={deals} people={people} />
                ) : (
                  <li key={item.id} className="agenda-row agenda-row--deadline">
                    <span className="agenda-row__time">Deadline</span>
                    <span className="agenda-row__title">{item.title}</span>
                  </li>
                ),
              )}
          </ul>
        </div>
      ))}
    </section>
  );
}

function MeetingRow({ meeting, deals, people }: { meeting: Meeting; deals: Deal[]; people: Person[] }) {
  const [open, setOpen] = useState(false);
  const deal = byId(deals, meeting.dealId);
  const time = `${formatTime(meeting.start)} to ${formatTime(meeting.end)}`;

  // Internal meetings have no counterparty to prepare for, so they get no prep card.
  if (meeting.attendeeIds.length === 0) {
    return (
      <li className="agenda-row">
        <span className="agenda-row__time">{time}</span>
        <span className="agenda-row__title">{meeting.title}</span>
      </li>
    );
  }

  const prepId = `prep-${meeting.id}`;
  return (
    <li>
      <button type="button" className="agenda-row agenda-row--button" aria-expanded={open} aria-controls={prepId} onClick={() => setOpen(!open)}>
        <span className="agenda-row__time">{time}</span>
        <span className="agenda-row__title">{meeting.title}</span>
        <span className="agenda-row__toggle">{open ? "Hide prep" : "Prep"}</span>
      </button>
      {open && (
        <div className="prep-card" id={prepId}>
          <p className="prep-card__label">Attendees</p>
          <ul className="prep-card__list">
            {meeting.attendeeIds.map((id) => {
              const person = byId(people, id);
              return (
                <li key={id}>
                  {person?.name} <span className="muted">{person?.org}</span>
                </li>
              );
            })}
          </ul>
          {deal && (
            <>
              <p className="prep-card__label">Deal</p>
              <p>{deal.codeName}, {deal.stage}. Next: {deal.nextStep}</p>
            </>
          )}
          <p className="prep-card__label">Last 3 interactions</p>
          <ul className="prep-card__list prep-card__dated">
            {meeting.recent.map((entry) => (
              <li key={entry.date + entry.text}>
                <span className="muted">{formatDate(entry.date)}</span>
                <span>{entry.text}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </li>
  );
}
