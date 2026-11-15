import { useSearchParams } from "react-router";
import { HISTORY_TYPES, type DealViewData } from "../../demo/types";
import { byId } from "../../lib/by-id";
import { anyOf, readList } from "../../lib/filters";
import { formatDate, formatWhen } from "../../lib/format";
import { EmptyState } from "../ui/empty-state";
import { FilterBar } from "../ui/filter-bar";
import { usePanel } from "./use-deal";

// PRD MH1 to MH3: next step pinned, every event newest first with its source, decisions marked.
export function HistoryTab({ data }: { data: DealViewData }) {
  const { openPanel } = usePanel();
  const [params] = useSearchParams();
  const types = readList(params, "type");
  const counterpartyIds = readList(params, "counterparty");
  const events = data.history.filter((event) => anyOf(types, [event.type]) && anyOf(counterpartyIds, event.counterpartyId ? [event.counterpartyId] : []));
  const owner = byId(data.users, data.deal.ownerId);

  return (
    <>
      {/* One line: what is next, then who owns it and when, so the events below stay in view. */}
      <div className="card pinned">
        <span className="pinned__label">Next step</span>
        <span className="pinned__text">{data.deal.nextStep}</span>
        <span className="pinned__meta">
          {owner?.name}
          {data.details.nextStepDue && `, due ${formatDate(data.details.nextStepDue)}`}
        </span>
      </div>

      <FilterBar
        shown={events.length}
        total={data.history.length}
        filters={[
          { kind: "list", key: "type", label: "Type", options: [...HISTORY_TYPES] },
          { kind: "list", key: "counterparty", label: data.deal.side === "sell" ? "Buyer" : "Target", options: data.counterparties.map((row) => ({ value: row.id, label: row.name })) },
        ]}
      >
        <button type="button" className="button button--quiet" onClick={() => openPanel("decision")}>
          Log decision
        </button>
      </FilterBar>

      {events.length === 0 ? (
        <EmptyState>Nothing matches these filters.</EmptyState>
      ) : (
        <ol className="card timeline">
          {events.map((event) => (
            <li key={event.id} className={event.decision ? "timeline__item timeline__item--decision" : "timeline__item"}>
              <span className="timeline__when">{formatWhen(event.at, data.now)}</span>
              <span className="timeline__body">
                <span className="timeline__type">{event.type}</span>
                <span>{event.text}</span>
                {event.decision && (
                  <span className="timeline__decision">
                    Decided by {event.decision.who}: {event.decision.why}
                  </span>
                )}
                <span className="timeline__source">Source: {event.source}</span>
              </span>
            </li>
          ))}
        </ol>
      )}
    </>
  );
}
