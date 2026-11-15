import { useState } from "react";
import type { Scorecard, ScorecardMetricInput } from "../../demo/types";
import { Drawer } from "../ui/drawer";
import { useRouteAction } from "../ui/toast";

const fromCard = (card: Scorecard): ScorecardMetricInput[] => card.metrics.map(({ id, label, kind, target }) => ({ id, label, kind, target }));

// Each person keeps their own list. Removing a metric drops its tags for this week; past weeks stay in Attio.
export function EditScorecardDrawer({ card, ownerName, onClose }: { card: Scorecard; ownerName: string; onClose: () => void }) {
  const act = useRouteAction("/scorecards");
  const [rows, setRows] = useState(() => fromCard(card));
  const dirty = JSON.stringify(rows) !== JSON.stringify(fromCard(card));
  const blocker = rows.some((row) => !row.label.trim())
    ? "Name every metric before saving."
    : rows.some((row) => row.kind === "count" && row.target < 1)
      ? "Set a target of 1 or more."
      : "";
  const update = (index: number, patch: Partial<ScorecardMetricInput>) => setRows(rows.map((row, i) => (i === index ? { ...row, ...patch } : row)));

  return (
    <Drawer
      title={`Edit ${ownerName}'s scorecard`}
      dirty={dirty}
      notice={blocker || undefined}
      onClose={onClose}
      actions={
        <button
          type="button"
          className="button"
          disabled={!dirty || Boolean(blocker)}
          onClick={() => {
            act({ intent: "metrics", ownerId: card.ownerId, metrics: JSON.stringify(rows.map((row) => ({ ...row, label: row.label.trim() }))) }, `${ownerName}'s scorecard saved.`);
            onClose();
          }}
        >
          Save
        </button>
      }
    >
      <section className="drawer__section">
        <ul className="metric-editor">
          {rows.map((row, index) => (
            <li key={row.id} className="metric-editor__row">
              <div className="field">
                <label htmlFor={`m-label-${row.id}`}>Metric</label>
                <input id={`m-label-${row.id}`} value={row.label} onChange={(event) => update(index, { label: event.target.value })} />
              </div>
              <div className="field">
                <label htmlFor={`m-kind-${row.id}`}>Type</label>
                <select id={`m-kind-${row.id}`} value={row.kind} onChange={(event) => update(index, { kind: event.target.value as ScorecardMetricInput["kind"] })}>
                  <option value="count">Count</option>
                  <option value="yes-no">Yes or no</option>
                </select>
              </div>
              <div className="field">
                <label htmlFor={`m-target-${row.id}`}>Weekly target</label>
                {row.kind === "count" ? (
                  <input id={`m-target-${row.id}`} type="number" min={1} value={row.target} onChange={(event) => update(index, { target: Number(event.target.value) })} />
                ) : (
                  <input id={`m-target-${row.id}`} value="Yes" disabled />
                )}
              </div>
              <button type="button" className="button button--small button--quiet metric-editor__remove" onClick={() => setRows(rows.filter((_, i) => i !== index))}>
                Remove
              </button>
            </li>
          ))}
        </ul>
        <button
          type="button"
          className="button button--small button--quiet"
          onClick={() => setRows([...rows, { id: `s-${Date.now()}`, label: "", kind: "count", target: 1 }])}
        >
          Add metric
        </button>
      </section>
    </Drawer>
  );
}
