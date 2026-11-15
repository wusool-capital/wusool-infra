import { useState } from "react";
import type { ActionEmail, Deal, Person } from "../../demo/types";
import { byId } from "../../lib/by-id";
import { findCodenameLeak } from "../../lib/codename";
import { formatDate, formatTime } from "../../lib/format";
import { Drawer } from "../ui/drawer";
import { useHomeAction } from "./home-context";

type EmailDrawerProps = { email: ActionEmail; deals: Deal[]; people: Person[]; onClose: () => void };

export function EmailDrawer({ email, deals, people, onClose }: EmailDrawerProps) {
  const act = useHomeAction();
  const [reply, setReply] = useState(email.draftReply);
  const from = byId(people, email.fromId);
  const deal = byId(deals, email.dealId);
  const leak = findCodenameLeak(reply, deal, from);
  const empty = reply.trim().length === 0;

  const send = () => {
    act({ intent: "email-send", id: email.id }, `Reply sent to ${from?.name}. Demo: nothing was sent.`);
    onClose();
  };

  const dismiss = () => {
    act({ intent: "email-dismiss", id: email.id }, "Marked not actionable. It stays in Gmail.");
    onClose();
  };

  return (
    <Drawer
      title={email.subject}
      status={[`${from?.name}, ${from?.org}`, deal?.codeName ?? "No deal linked", `${formatDate(email.receivedAt)} ${formatTime(email.receivedAt)}`].join(" · ")}
      dirty={reply !== email.draftReply}
      onClose={onClose}
      notice={leak ? `Remove "${leak}" before sending. Buyers only see the code name.` : empty && "Write a reply before sending."}
      actions={
        <>
          <button type="button" className="button button--quiet" onClick={dismiss}>
            Not actionable
          </button>
          <button type="button" className="button" disabled={Boolean(leak) || empty} onClick={send}>
            Send
          </button>
        </>
      }
    >
      <section className="drawer__section">
        <h3 className="panel-heading">Message</h3>
        <p className="message-body">{email.message}</p>
      </section>
      <section className="drawer__section">
        <div className="drawer__section-head">
          <h3 className="panel-heading">Reply</h3>
          <span className="badge">AI draft</span>
        </div>
        <div className="field">
          <label htmlFor="reply-body">Reply to {from?.name}</label>
          <textarea id="reply-body" rows={10} value={reply} onChange={(event) => setReply(event.target.value)} />
        </div>
      </section>
    </Drawer>
  );
}
