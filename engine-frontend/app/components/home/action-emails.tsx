import { Link } from "react-router";
import type { ActionEmail, Deal, Person } from "../../demo/types";
import { byId } from "../../lib/by-id";
import { formatWhen, hoursBetween } from "../../lib/format";
import { EmptyState } from "../ui/empty-state";
import { OverdueMark } from "../ui/overdue-mark";

// PRD success metric: no deal email left without a reply after 24 hours.
const REPLY_DUE_HOURS = 24;

export function isReplyOverdue(email: ActionEmail, now: string) {
  return hoursBetween(email.receivedAt, now) > REPLY_DUE_HOURS;
}

type ActionEmailsProps = { emails: ActionEmail[]; deals: Deal[]; people: Person[]; now: string };

export function ActionEmails({ emails, deals, people, now }: ActionEmailsProps) {
  return (
    <section className="card" aria-labelledby="emails-title">
      <div className="card__head">
        <h2 id="emails-title" className="section-title">To reply</h2>
        <span className="card__meta">{emails.length} need a reply or action</span>
      </div>
      {emails.length === 0 ? (
        <EmptyState>No email needs action.</EmptyState>
      ) : (
        <ul className="review-list">
          {emails.map((email) => {
            const from = byId(people, email.fromId);
            const deal = byId(deals, email.dealId);
            return (
              // Same two-line row as Review. The whole row opens the reply drawer, so Reply is
              // drawn as a button but is part of the one link (no button inside a link).
              <li key={email.id}>
                <Link className="needs-row needs-row--link" to={`?email=${email.id}`} preventScrollReset>
                  <span className="needs-row__title">
                    <span className="needs-row__from">{from?.name}</span> {email.subject}
                  </span>
                  <span className="needs-row__actions">
                    <span className="needs-row__when">
                      {isReplyOverdue(email, now) && <OverdueMark />}
                      {formatWhen(email.receivedAt, now)}
                    </span>
                    <span className="button button--small" aria-hidden="true">
                      Reply
                    </span>
                  </span>
                  <span className="needs-row__context">
                    {deal ? <span className="badge needs-row__chip">{deal.codeName}</span> : <span className="chip needs-row__chip">No deal</span>}
                    <span className="needs-row__summary">
                      {from?.org}. Suggested: {email.suggestedAction}
                    </span>
                  </span>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
