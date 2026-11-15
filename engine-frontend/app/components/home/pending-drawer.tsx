import { useState } from "react";
import type { Deal, DraftTask, PendingEdit, PendingItem, Person } from "../../demo/types";
import { byId } from "../../lib/by-id";
import { STAGES, type Stage } from "../../lib/stages";
import { Drawer } from "../ui/drawer";
import { useHomeAction } from "./home-context";
import { approveLabel, approvedNotice, pendingLeak } from "./pending-review";

// `generated`: opened from the row's Generate email button, so the follow-up draft is written already.
type PendingDrawerProps = { item: PendingItem; generated?: boolean; deals: Deal[]; people: Person[]; onClose: () => void };

function initialEdit(item: PendingItem): PendingEdit {
  switch (item.kind) {
    case "email":
    case "follow-up":
      return { body: item.body };
    case "stage-change":
      return { toStage: item.toStage };
    case "tasks":
      return { tasks: item.tasks };
    case "next-step":
      return { nextStep: item.nextStep };
  }
}

export function PendingDrawer({ item, generated = false, deals, people, onClose }: PendingDrawerProps) {
  const act = useHomeAction();
  const [hasDraft, setHasDraft] = useState(item.kind !== "follow-up" || generated);
  const [edit, setEdit] = useState(() => initialEdit(item));
  const dirty = JSON.stringify(edit) !== JSON.stringify(initialEdit(item));
  const leak = pendingLeak(item, edit.body ?? "", deals, people);
  const deal = byId(deals, "dealId" in item ? item.dealId : undefined);

  const approve = () => {
    act({ intent: "pending-approve", id: item.id, edit: JSON.stringify(edit) }, approvedNotice(item, edit, deals, people));
    onClose();
  };

  const setTask = (index: number, patch: Partial<DraftTask>) =>
    setEdit({ tasks: edit.tasks!.map((task, i) => (i === index ? { ...task, ...patch } : task)) });

  return (
    <Drawer
      title={item.title}
      status={[deal?.codeName, `Source: ${item.source}`].filter(Boolean).join(" · ")}
      dirty={dirty}
      onClose={onClose}
      notice={leak && `Remove "${leak}" before sending. Buyers only see the code name.`}
      actions={
        <button type="button" className="button" disabled={Boolean(leak) || !hasDraft} onClick={approve}>
          {approveLabel(item)}
        </button>
      }
    >
      {item.kind === "follow-up" && !hasDraft ? (
        <section className="drawer__section">
          <p>{item.reason}</p>
          <button type="button" className="button button--small" onClick={() => setHasDraft(true)}>
            Generate email
          </button>
        </section>
      ) : (
        <section className="drawer__section">
          <div className="drawer__section-head">
            <h3 className="panel-heading">Draft</h3>
            <span className="badge">AI draft</span>
          </div>

          {item.kind === "follow-up" && <p className="muted">{item.reason}</p>}

          {(item.kind === "email" || item.kind === "follow-up") && (
            <div className="field">
              <label htmlFor="pending-body">Email to {byId(people, item.toId)?.name}</label>
              <textarea id="pending-body" rows={12} value={edit.body} onChange={(event) => setEdit({ body: event.target.value })} />
            </div>
          )}

          {item.kind === "stage-change" && (
            <>
              <p>{item.evidence}</p>
              <div className="field">
                <label htmlFor="pending-stage">Move {deal?.codeName} to</label>
                <select id="pending-stage" value={edit.toStage} onChange={(event) => setEdit({ toStage: event.target.value as Stage })}>
                  {STAGES.map((stage) => (
                    <option key={stage}>{stage}</option>
                  ))}
                </select>
              </div>
            </>
          )}

          {item.kind === "next-step" && (
            <div className="field">
              <label htmlFor="pending-next">Next step on {deal?.codeName}</label>
              <input id="pending-next" value={edit.nextStep} onChange={(event) => setEdit({ nextStep: event.target.value })} />
            </div>
          )}

          {item.kind === "tasks" &&
            edit.tasks!.map((task, index) => (
              <div className="task-edit" key={index}>
                <div className="field">
                  <label htmlFor={`task-title-${index}`}>Task {index + 1}</label>
                  <input id={`task-title-${index}`} value={task.title} onChange={(event) => setTask(index, { title: event.target.value })} />
                </div>
                <div className="field">
                  <label htmlFor={`task-due-${index}`}>Due</label>
                  <input id={`task-due-${index}`} type="date" value={task.dueDate} onChange={(event) => setTask(index, { dueDate: event.target.value })} />
                </div>
              </div>
            ))}
        </section>
      )}
    </Drawer>
  );
}
