import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { WORKSTREAM_STATUSES, type Workstream, type WorkstreamStatus } from "../../demo/types";
import { formatDate } from "../../lib/format";
import { EmptyState } from "../ui/empty-state";
import { ActionsMenu } from "../ui/actions-menu";
import { useAnchored } from "../ui/use-anchored";
import { useDismiss } from "../ui/use-dismiss";
import { useHomeAction } from "./home-context";

export function Workstreams({ workstreams }: { workstreams: Workstream[] }) {
  return (
    <section className="card home__desktop-only" aria-labelledby="workstreams-title">
      <div className="card__head">
        <h2 id="workstreams-title" className="section-title">Workstreams</h2>
        <span className="card__meta">From Notion</span>
      </div>
      {workstreams.length === 0 ? (
        <EmptyState>No active workstreams.</EmptyState>
      ) : (
        <table className="table table--fixed">
          <colgroup>
            {/* Fits the half-width Home cell: Status is fixed to fit its pill, the due date sits under
                the name, and the last narrow column holds the row menu. */}
            <col style={{ width: "34%" }} />
            <col style={{ width: "136px" }} />
            <col />
            <col style={{ width: "60px" }} />
          </colgroup>
          <thead>
            <tr>
              <th scope="col">Workstream</th>
              <th scope="col">Status</th>
              <th scope="col">Next step</th>
              <th scope="col">
                <span className="visually-hidden">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {workstreams.map((workstream) => (
              <WorkstreamRow key={workstream.id} workstream={workstream} />
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

const ROW_ACTIONS = [{ panel: "delete", label: "Delete workstream" }] as const;

// Name, due date and next step are edited in place; delete asks once inside the row (no second
// layer) because it removes the Notion page (it goes to Notion's trash, where it can be restored).
function WorkstreamRow({ workstream }: { workstream: Workstream }) {
  const act = useHomeAction();
  const [confirming, setConfirming] = useState(false);

  if (confirming) {
    return (
      <tr>
        <td colSpan={4}>
          <div className="row-confirm" role="alert">
            <span>
              Delete <strong>{workstream.name}</strong>? It moves to Notion's trash.
            </span>
            <button
              type="button"
              className="button button--small"
              autoFocus
              onClick={() => act({ intent: "workstream-delete", id: workstream.id }, `${workstream.name} deleted. Restore it from Notion's trash if needed.`)}
            >
              Delete
            </button>
            <button type="button" className="text-button" onClick={() => setConfirming(false)}>
              Cancel
            </button>
          </div>
        </td>
      </tr>
    );
  }

  return (
    <tr>
      <td>
        <InlineField
          type="text"
          value={workstream.name}
          display={workstream.name}
          label={`Name of ${workstream.name}`}
          className="inline-edit--title"
          onSave={(name) => act({ intent: "workstream-name", id: workstream.id, name }, `Renamed to ${name}.`)}
        />
        {/* The due date belongs to the workstream; it writes back to Notion like status and next step. */}
        <InlineField
          type="date"
          value={workstream.dueDate}
          display={`Due ${formatDate(workstream.dueDate)}`}
          label={`Due date for ${workstream.name}`}
          className="inline-edit--sub"
          onSave={(dueDate) => act({ intent: "workstream-due", id: workstream.id, dueDate }, `${workstream.name}: due ${formatDate(dueDate)}.`)}
        />
      </td>
      <td>
        <StatusMenu workstream={workstream} />
      </td>
      <td>
        <InlineField
          type="text"
          value={workstream.nextStep}
          display={workstream.nextStep}
          label={`Next step for ${workstream.name}`}
          onSave={(nextStep) => act({ intent: "workstream-next-step", id: workstream.id, nextStep }, `${workstream.name}: next step saved.`)}
        />
      </td>
      <td>
        <ActionsMenu itemName={workstream.name} actions={ROW_ACTIONS} onPick={() => setConfirming(true)} />
      </td>
    </tr>
  );
}

const STATUS_TONES: Record<WorkstreamStatus, string> = {
  "Not started": "chip",
  "In progress": "chip chip--progress",
  Blocked: "chip chip--alert",
  Done: "chip chip--done",
};

function StatusMenu({ workstream }: { workstream: Workstream }) {
  const act = useHomeAction();
  const [open, setOpen] = useState(false);
  const dismiss = useDismiss<HTMLDivElement, HTMLUListElement>(open, () => setOpen(false));
  const anchor = useAnchored(open, () => setOpen(false));

  const toggle = () => {
    anchor.place();
    setOpen(!open);
  };

  const pick = (status: WorkstreamStatus) => {
    setOpen(false);
    if (status !== workstream.status) {
      act({ intent: "workstream-status", id: workstream.id, status }, `${workstream.name}: status set to ${status}.`);
    }
  };

  return (
    <div
      className="chip-menu"
      ref={dismiss.ref}
      onBlur={dismiss.onBlur}
      onKeyDown={(event) => {
        if (event.key === "Escape") setOpen(false);
      }}
    >
      <button
        ref={anchor.triggerRef}
        type="button"
        className={`${STATUS_TONES[workstream.status]} chip--button`}
        aria-haspopup="true"
        aria-expanded={open}
        aria-label={`Status: ${workstream.status}. Change status`}
        onClick={toggle}
      >
        {workstream.status} ▾
      </button>
      {open &&
        createPortal(
          <ul
            ref={dismiss.panelRef}
            className="chip-menu__list chip-menu__list--fixed"
            style={anchor.style}
            onKeyDown={(event) => event.key === "Escape" && setOpen(false)}
          >
            {WORKSTREAM_STATUSES.map((status) => (
              <li key={status}>
                <button type="button" className="chip-menu__option" aria-current={status === workstream.status} onClick={() => pick(status)}>
                  {status}
                </button>
              </li>
            ))}
          </ul>,
          document.body,
        )}
    </div>
  );
}

type InlineFieldProps = {
  type: "text" | "date";
  value: string;
  display: string;
  label: string;
  className?: string;
  onSave: (value: string) => void;
};

/** Click the value, change it, Save: two clicks, and Escape cancels. */
function InlineField({ type, value: saved, display, label, className = "", onSave }: InlineFieldProps) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(saved);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const wasEditing = useRef(false);

  // Return focus to the cell after Save or Cancel so keyboard users keep their place.
  useEffect(() => {
    if (!editing && wasEditing.current) buttonRef.current?.focus();
    wasEditing.current = editing;
  }, [editing]);

  if (!editing) {
    return (
      <button
        ref={buttonRef}
        type="button"
        className={`inline-edit ${className}`}
        onClick={() => {
          setValue(saved);
          setEditing(true);
        }}
      >
        {display}
        <span className="visually-hidden">. Edit {label.toLowerCase()}</span>
      </button>
    );
  }

  return (
    <form
      className="inline-form"
      onSubmit={(event) => {
        event.preventDefault();
        if (!value.trim()) return;
        onSave(value.trim());
        setEditing(false);
      }}
      onKeyDown={(event) => {
        if (event.key === "Escape") setEditing(false);
      }}
    >
      <input type={type} aria-label={label} value={value} onChange={(event) => setValue(event.target.value)} onFocus={(event) => type === "text" && event.target.select()} autoFocus />
      <button type="submit" className="button button--small" disabled={!value.trim()}>
        Save
      </button>
      <button type="button" className="text-button" onClick={() => setEditing(false)}>
        Cancel
      </button>
    </form>
  );
}
