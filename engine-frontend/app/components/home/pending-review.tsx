import { X } from "@phosphor-icons/react";
import { useNavigate } from "react-router";
import type { Deal, PendingEdit, PendingItem, Person } from "../../demo/types";
import { byId } from "../../lib/by-id";
import { findCodenameLeak } from "../../lib/codename";
import { EmptyState } from "../ui/empty-state";
import { useHomeAction } from "./home-context";

const KIND_LABELS: Record<PendingItem["kind"], string> = {
  email: "Email draft",
  "follow-up": "Follow-up",
  "stage-change": "Stage change",
  tasks: "Tasks",
  "next-step": "Next step",
};

export function approveLabel(item: PendingItem) {
  if (item.kind === "follow-up") return "Send";
  return item.kind === "email" ? "Approve and send" : "Approve";
}

/** Confirms what an approval did, in the words the user would use. */
export function approvedNotice(item: PendingItem, edit: PendingEdit, deals: Deal[], people: Person[]) {
  const deal = byId(deals, "dealId" in item ? item.dealId : undefined);
  switch (item.kind) {
    case "email":
    case "follow-up":
      return `Sent to ${byId(people, item.toId)?.name}. Demo: nothing was sent.`;
    case "stage-change":
      return `${deal?.codeName} moved to ${edit.toStage ?? item.toStage}.`;
    case "tasks":
      return `${(edit.tasks ?? item.tasks).length} tasks added to Attio.`;
    case "next-step":
      return `Next step updated on ${deal?.codeName}.`;
  }
}

/** Codename check for email drafts; null when the draft may be sent. */
export function pendingLeak(item: PendingItem, body: string, deals: Deal[], people: Person[]) {
  if (item.kind !== "email" && item.kind !== "follow-up") return null;
  return findCodenameLeak(body, byId(deals, item.dealId), byId(people, item.toId));
}

type PendingReviewProps = { title?: string; items: PendingItem[]; deals: Deal[]; people: Person[] };

export function PendingReview({ title = "Pending review", items, deals, people }: PendingReviewProps) {
  const act = useHomeAction();
  const navigate = useNavigate();
  const open = (item: PendingItem, generate = false) => navigate(`?review=${item.id}${generate ? "&generate=1" : ""}`, { preventScrollReset: true });

  return (
    <section className="card" aria-labelledby={`${title.toLowerCase().replaceAll(" ", "-")}-title`}>
      <div className="card__head">
        <h2 id={`${title.toLowerCase().replaceAll(" ", "-")}-title`} className="section-title">{title}</h2>
        <span className="card__meta">{items.length} to review</span>
      </div>
      {items.length === 0 ? (
        <EmptyState>Nothing to review.</EmptyState>
      ) : (
        <ul className="review-list">
          {items.map((item) => {
            const leak = pendingLeak(item, item.kind === "email" ? item.body : "", deals, people);
            // The buttons act on their own; a click anywhere else on the row opens the side panel.
            const stop = (event: React.MouseEvent) => event.stopPropagation();
            return (
              // Two lines: what to approve and the buttons, then one line of context.
              <li
                key={item.id}
                className="needs-row needs-row--clickable"
                tabIndex={0}
                aria-label={`Open ${item.title}`}
                onClick={() => open(item)}
                onKeyDown={(event) => event.key === "Enter" && event.target === event.currentTarget && open(item)}
              >
                <p className="needs-row__title">{item.title}</p>
                <div className="needs-row__actions" onClick={stop}>
                  {item.kind === "follow-up" ? (
                    // No draft exists until someone asks for one; the panel opens with it written.
                    <button type="button" className="button button--small" onClick={() => open(item, true)}>
                      Generate email
                    </button>
                  ) : (
                    <button
                      type="button"
                      className="button button--small"
                      disabled={Boolean(leak)}
                      onClick={() => act({ intent: "pending-approve", id: item.id, edit: "{}" }, approvedNotice(item, {}, deals, people))}
                    >
                      {approveLabel(item)}
                    </button>
                  )}
                  <button type="button" className="button button--small button--quiet" onClick={() => act({ intent: "pending-reject", id: item.id }, `Rejected: ${item.title}.`)}>
                    <X size={12} weight="bold" aria-hidden="true" />
                    Reject
                  </button>
                </div>
                <p className="needs-row__context">
                  <span className="chip needs-row__chip">{KIND_LABELS[item.kind]}</span>
                  {leak ? (
                    <span className="needs-row__warning">Remove "{leak}" before sending. Buyers only see the code name.</span>
                  ) : (
                    <span className="needs-row__summary">{summaryLine(item, deals, people)}</span>
                  )}
                </p>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

/** One line of context per item; the row cuts it with an ellipsis. */
function summaryLine(item: PendingItem, deals: Deal[], people: Person[]) {
  const deal = byId(deals, "dealId" in item ? item.dealId : undefined);
  switch (item.kind) {
    case "follow-up":
      return `To ${byId(people, item.toId)?.name}${deal ? `, ${deal.codeName}` : ""}. ${item.reason}`;
    case "email": {
      // Skip the greeting so the line shows the message itself.
      const message = item.body.replace(/\s+/g, " ").replace(/^(Dear|Hi|Hello) [^,]+, /, "");
      return `To ${byId(people, item.toId)?.name}${deal ? `, ${deal.codeName}` : ""}. ${message}`;
    }
    case "stage-change":
      return `${deal?.codeName}, ${deal?.stage} to ${item.toStage}. ${item.evidence}`;
    case "next-step":
      return `${deal?.codeName}: ${item.nextStep}`;
    case "tasks": {
      const [first, ...rest] = item.tasks;
      return `${deal ? `${deal.codeName}: ` : ""}${first?.title ?? ""}${rest.length ? ` and ${rest.length} more` : ""}`;
    }
  }
}
