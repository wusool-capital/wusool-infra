import { CheckCircle, X } from "@phosphor-icons/react";
import { useState } from "react";
import { useSearchParams } from "react-router";
import { EditScorecardDrawer } from "../components/scorecards/edit-scorecard-drawer";
import { MetAdder } from "../components/scorecards/met-adder";
import { MetricStatusChip } from "../components/scorecards/metric-status-chip";
import { EmptyState } from "../components/ui/empty-state";
import { useRouteAction } from "../components/ui/toast";
import { CURRENT_USER_ID, getScorecards, setScorecardDone, setScorecardMetrics, tagScorecard, untagScorecard } from "../demo/api";
import type { Scorecard, ScorecardMetric, ScorecardMetricInput, ScorecardsData, ScorecardWeek, UserId } from "../demo/types";
import { byId } from "../lib/by-id";
import { formatDate } from "../lib/format";
import { metricState } from "../lib/scorecard";
import type { Route } from "./+types/scorecards";
import { Segmented } from "../components/ui/segmented";

export async function clientLoader() {
  return getScorecards();
}

export async function clientAction({ request }: Route.ClientActionArgs) {
  const form = await request.formData();
  const field = (name: string) => String(form.get(name) ?? "");
  const ownerId = field("ownerId") as UserId;
  switch (field("intent")) {
    case "tag":
      return tagScorecard(ownerId, field("metricId"), field("personId"), CURRENT_USER_ID);
    case "untag":
      return untagScorecard(ownerId, field("metricId"), field("personId"));
    case "done":
      return setScorecardDone(ownerId, field("metricId"), field("done") === "true");
    case "metrics":
      return setScorecardMetrics(ownerId, JSON.parse(field("metrics")) as ScorecardMetricInput[]);
  }
}

// PRD K1 to K4: this week's numbers with a pace-based status, the people behind each count,
// and the last eight weeks, newest first. Each person keeps their own list of metrics.
export default function Scorecards({ loaderData: data }: Route.ComponentProps) {
  const [params, setParams] = useSearchParams();
  const people = data.users.filter((user) => data.scorecards.some((card) => card.ownerId === user.id));
  // One person at a time, so the page stays one card long. Defaults to the signed-in user.
  const card = data.scorecards.find((row) => row.ownerId === params.get("person")) ?? data.scorecards.find((row) => row.ownerId === data.currentUserId);
  const [editing, setEditing] = useState<UserId | null>(null);
  const editingCard = data.scorecards.find((card) => card.ownerId === editing);

  return (
    <>
      <h1 className="page-title">Scorecards</h1>
      <div className="toolbar">
        <Segmented role="group" aria-label="Person">
          {people.map((user) => (
            <button key={user.id} type="button" className="segmented__option" aria-pressed={card?.ownerId === user.id} onClick={() => setParams({ person: user.id }, { preventScrollReset: true })}>
              {user.name}
            </button>
          ))}
        </Segmented>
        <span className="toolbar__count">Week of {formatDate(data.scorecards[0]?.weekOf ?? data.now)}</span>
      </div>
      <div className="page-body">
        {card ? (
          <ScorecardCard key={card.ownerId} card={card} data={data} onEdit={() => setEditing(card.ownerId)} />
        ) : (
          <EmptyState>No scorecard for this person yet.</EmptyState>
        )}
      </div>
      {editingCard && <EditScorecardDrawer key={editingCard.ownerId} card={editingCard} ownerName={byId(data.users, editingCard.ownerId)?.name ?? ""} onClose={() => setEditing(null)} />}
    </>
  );
}

function ScorecardCard({ card, data, onEdit }: { card: Scorecard; data: ScorecardsData; onEdit: () => void }) {
  const owner = byId(data.users, card.ownerId);
  // Newest week first, so the latest result sits next to the metric name.
  const weeks = data.history.filter((week) => week.ownerId === card.ownerId).sort((a, b) => b.weekOf.localeCompare(a.weekOf));

  return (
    <section className="card" aria-labelledby={`card-${card.ownerId}`}>
      <div className="card__head">
        <h2 id={`card-${card.ownerId}`} className="section-title">{owner?.name}</h2>
        <span className="card__meta">{card.workdaysElapsed} of 5 working days done</span>
        <button type="button" className="button button--small button--quiet" onClick={onEdit}>
          Edit scorecard
        </button>
      </div>

      <div className="metric-tiles">
        {card.metrics.map((metric) => (
          <MetricTile key={metric.id} card={card} metric={metric} data={data} />
        ))}
      </div>

      <h3 className="panel-heading scorecard__subhead">Last 8 weeks</h3>
      <HistoryTable card={card} weeks={weeks} />
    </section>
  );
}

function MetricTile({ card, metric, data }: { card: Scorecard; metric: ScorecardMetric; data: ScorecardsData }) {
  const act = useRouteAction("/scorecards");
  const status = <MetricStatusChip status={metricState(metric, card.workdaysElapsed)} />;

  if (metric.kind === "yes-no") {
    return (
      <div className="metric-tile">
        <p className="metric-tile__label">{metric.label}</p>
        <p className="metric-tile__value">{metric.done ? "Yes" : "No"}</p>
        {status}
        <Segmented role="group" aria-label={`${metric.label} this week`}>
          {[true, false].map((value) => (
            <button
              key={String(value)}
              type="button"
              className="segmented__option"
              aria-pressed={Boolean(metric.done) === value}
              onClick={() => act({ intent: "done", ownerId: card.ownerId, metricId: metric.id, done: String(value) }, `${metric.label}: ${value ? "yes" : "no"} this week.`)}
            >
              {value ? "Yes" : "No"}
            </button>
          ))}
        </Segmented>
      </div>
    );
  }

  return (
    <div className="metric-tile">
      <p className="metric-tile__label">{metric.label}</p>
      <p className="metric-tile__value">
        {metric.taggedIds.length}
        <span className="metric-tile__target"> of {metric.target}</span>
      </p>
      {status}
      {/* The count comes from these tags, like the Attio "Met" fields. */}
      {metric.taggedIds.length > 0 && (
        <ul className="tag-list" aria-label={`Tagged for ${metric.label}`}>
          {metric.taggedIds.map((id) => {
            const person = byId(data.people, id);
            return (
              <li key={id} className="tag">
                <span className="tag__text">
                  <span className="tag__name">{person?.name}</span>
                  <span className="tag__org">{person?.org}</span>
                </span>
                <button
                  type="button"
                  className="tag__remove"
                  aria-label={`Remove ${person?.name} from ${metric.label}`}
                  onClick={() => act({ intent: "untag", ownerId: card.ownerId, metricId: metric.id, personId: id }, `${person?.name} removed from ${metric.label}.`)}
                >
                  <X size={12} weight="bold" aria-hidden="true" />
                </button>
              </li>
            );
          })}
        </ul>
      )}
      <MetAdder
        id={`tag-${card.ownerId}-${metric.id}`}
        addLabel="Tag a person"
        people={data.people}
        metIds={metric.taggedIds}
        suggestedIds={card.suggestedPersonIds}
        onAdd={(person) => act({ intent: "tag", ownerId: card.ownerId, metricId: metric.id, personId: person.id }, `${person.name} tagged on ${metric.label}.`)}
      />
    </div>
  );
}

// At or above target: green with a check. Below: red. The check means the result never rests on colour alone.
function HistoryTable({ card, weeks }: { card: Scorecard; weeks: ScorecardWeek[] }) {
  return (
    <div className="table-scroll">
      <table className="table history-table">
        <thead>
          <tr>
            <th scope="col">Metric</th>
            {weeks.map((week) => (
              <th key={week.weekOf} scope="col" className="num">
                {formatDate(week.weekOf).replace(/ \d{4}$/, "")}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {card.metrics.map((metric) => (
            <tr key={metric.id}>
              <td>
                {metric.label}
                {metric.kind === "count" && <span className="muted"> (target {metric.target})</span>}
              </td>
              {weeks.map((week) => {
                const value = week.actuals[metric.id];
                if (value === undefined) return <td key={week.weekOf} className="num muted">Not tracked</td>;
                const hit = value >= metric.target;
                return (
                  <td key={week.weekOf} className="num">
                    <span className={hit ? "history-cell history-cell--hit" : "history-cell history-cell--miss"}>
                      {hit && <CheckCircle size={14} weight="fill" aria-label="On target" />}
                      {metric.kind === "yes-no" ? (value ? "Yes" : "No") : value}
                    </span>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
