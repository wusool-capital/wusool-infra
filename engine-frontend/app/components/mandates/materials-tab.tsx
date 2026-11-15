import type { DealViewData, Material, MaterialStatus } from "../../demo/types";
import { formatDate } from "../../lib/format";
import { EmptyState } from "../ui/empty-state";
import { inHand, missingFromClient } from "./materials";
import { usePanel } from "./use-deal";

const TONES: Record<MaterialStatus, string> = {
  "Not started": "chip",
  Drafted: "chip chip--progress",
  Sent: "chip chip--progress",
  Signed: "chip chip--done",
  Approved: "chip chip--done",
  Live: "chip chip--done",
};

// PRD MM1 and MM2: one card per document, in the order the deal needs them. Each opens its checklist.
export function MaterialsTab({ data }: { data: DealViewData }) {
  const { openPanel } = usePanel();
  if (data.materials.length === 0) return <EmptyState>No materials tracked for this deal yet.</EmptyState>;

  return (
    <div className="material-grid">
      {data.materials.map((material) => {
        const have = inHand(material);
        const toAsk = missingFromClient(material).length;
        return (
          <button key={material.id} type="button" className="material-card" onClick={() => openPanel(`material:${material.id}`)}>
            <span className="material-card__head">
              <span className="material-card__name">{material.name}</span>
              <span className={TONES[material.status]}>{material.status}</span>
            </span>
            {/* One line: the date once done, the gap while incomplete. */}
            {have === material.items.length ? (
              <span className="material-card__when">{whenLine(material)}</span>
            ) : (
              <span className="material-card__progress">
                <span className="progress" aria-hidden="true">
                  <span className="progress__fill" style={{ width: `${(have / material.items.length) * 100}%` }} />
                </span>
                <span className="material-card__count">
                  {toAsk > 0 ? (
                    <>
                      <span className="overdue__dot" aria-hidden="true">!</span> {toAsk} to ask the client
                    </>
                  ) : (
                    `${have} of ${material.items.length} in hand`
                  )}
                </span>
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

function whenLine(material: Material) {
  if (material.status === "Signed" && material.date) return `Signed ${formatDate(material.date)}`;
  if (material.status === "Sent" && material.date) return `Sent ${formatDate(material.date)}`;
  if (material.status === "Live" && material.date) return `Live since ${formatDate(material.date)}`;
  if (material.version) return `${material.version}${material.status === "Approved" ? ", approved" : ", in review"}`;
  return "Nothing drafted yet";
}
