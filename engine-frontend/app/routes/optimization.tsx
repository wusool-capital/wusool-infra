import { BottleneckButton } from "../components/optimization/bottleneck-button";
import { EmptyState } from "../components/ui/empty-state";
import { OverdueMark } from "../components/ui/overdue-mark";
import { useNotice, useRouteAction } from "../components/ui/toast";
import { CURRENT_USER_ID, getOptimization, logBottleneck, promoteBottleneck } from "../demo/api";
import type { OptimizationData } from "../demo/types";
import { byId } from "../lib/by-id";
import { followUp } from "../lib/follow-ups";
import { count, dayKey, formatDate, formatWhen, hoursBetween } from "../lib/format";
import { STAGES } from "../lib/stages";
import type { Route } from "./+types/optimization";

export async function clientLoader() {
  return getOptimization();
}

export async function clientAction({ request }: Route.ClientActionArgs) {
  const form = await request.formData();
  const field = (name: string) => String(form.get(name) ?? "");
  switch (field("intent")) {
    case "log-bottleneck":
      return logBottleneck(CURRENT_USER_ID, field("what"), field("where"), field("dealId"));
    case "promote":
      return promoteBottleneck(field("id"));
  }
}

const days = (from: string, now: string) => Math.floor(hoursBetween(from, now) / 24);
const percent = (part: number, whole: number) => (whole ? `${Math.round((part / whole) * 100)}%` : "Not set");

// Every view here is computed by rules from logged activity, never by AI (CLAUDE.md AI usage policy).
function computeViews(data: OptimizationData) {
  const today = dayKey(data.now);
  const missed = data.counterparties
    .map((row) => ({ row, step: followUp(row) }))
    .filter(({ step }) => step.state === "due" && step.date < today)
    .map(({ row, step }) => ({ row, due: step.state === "due" ? step.date : "" }))
    .sort((a, b) => a.due.localeCompare(b.due));
  const inStage = data.deals
    .filter((deal) => deal.status === "Active" && data.stageEnteredAt[deal.id])
    .map((deal) => ({ deal, days: days(data.stageEnteredAt[deal.id], data.now), median: data.stageMedianDays[deal.stage] ?? 0 }))
    .sort((a, b) => b.days - b.median - (a.days - a.median));
  const overMedian = inStage.filter((row) => row.median && row.days > row.median);
  const waiting = data.waitingClients.filter((row) => days(row.lastFromClientAt, data.now) >= 7);
  const bestTemplate = [...data.replyStats].sort((a, b) => b.replied / b.sent - a.replied / a.sent)[0];
  const weekStart = "2026-11-09";
  const newBottlenecks = data.bottlenecks.filter((row) => dayKey(row.at) >= weekStart);
  return { missed, inStage, overMedian, waiting, bestTemplate, newBottlenecks };
}

export default function Optimization({ loaderData: data }: Route.ComponentProps) {
  const act = useRouteAction("/optimization");
  const notice = useNotice();
  const views = computeViews(data);
  const summary = [
    `${count(views.missed.length, "follow-up is", "follow-ups are")} overdue across deals and seller lists.`,
    `${count(views.overMedian.length, "deal sits", "deals sit")} longer than the median in their stage: ${views.overMedian.map(({ deal }) => deal.codeName).join(", ") || "none"}.`,
    `${count(views.waiting.length, "client has", "clients have")} waited 7 days or more for a reply.`,
    views.bestTemplate && `Best reply rate: ${views.bestTemplate.template} in ${views.bestTemplate.sector} (${percent(views.bestTemplate.replied, views.bestTemplate.sent)}).`,
    `${count(views.newBottlenecks.length, "bottleneck", "bottlenecks")} logged this week.`,
  ].filter(Boolean) as string[];

  return (
    <>
      <div className="page-head">
        <h1 className="page-title">Engine optimization</h1>
        <BottleneckButton deals={data.deals} />
      </div>

      <div className="page-body">
        <section className="card" aria-labelledby="summary-title">
          <div className="card__head">
            <h2 id="summary-title" className="section-title">Weekly summary</h2>
            <span className="card__meta">For the team meeting, week of 9 Nov 2026</span>
            <button type="button" className="button button--small button--quiet" onClick={() => navigator.clipboard?.writeText(summary.join("\n")).then(() => notice("Summary copied. Paste it in the meeting notes."))}>
              Copy summary
            </button>
          </div>
          <ul className="summary-list">
            {summary.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </section>

        <div className="opt-grid">
          <section className="card" aria-labelledby="missed-title">
            <div className="card__head">
              <h2 id="missed-title" className="section-title">Missed follow-ups</h2>
              <span className="card__meta">{views.missed.length}</span>
            </div>
            {views.missed.length === 0 ? (
              <EmptyState>No follow-up is overdue.</EmptyState>
            ) : (
              <table className="table">
                <thead>
                  <tr>
                    <th scope="col">Counterparty</th>
                    <th scope="col">Deal or list</th>
                    <th scope="col">Due</th>
                  </tr>
                </thead>
                <tbody>
                  {views.missed.map(({ row, due }) => (
                    <tr key={row.id}>
                      <td>{row.name}</td>
                      <td className="cell-clip">{byId(data.deals, row.dealId || undefined)?.codeName ?? row.listName}</td>
                      <td>
                        <span className="follow-up-line">
                          <OverdueMark /> {formatDate(due)}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>

          <section className="card" aria-labelledby="waiting-title">
            <div className="card__head">
              <h2 id="waiting-title" className="section-title">Clients waiting 7 days or more</h2>
              <span className="card__meta">{views.waiting.length}</span>
            </div>
            {views.waiting.length === 0 ? (
              <EmptyState>Every client has had a reply within 7 days.</EmptyState>
            ) : (
              <table className="table">
                <thead>
                  <tr>
                    <th scope="col">Client</th>
                    <th scope="col">Deal</th>
                    <th scope="col">Last message</th>
                    <th scope="col" className="num">Days</th>
                  </tr>
                </thead>
                <tbody>
                  {views.waiting.map((row) => (
                    <tr key={row.id}>
                      <td>{byId(data.people, row.personId)?.name}</td>
                      <td>{byId(data.deals, row.dealId)?.codeName}</td>
                      <td className="cell-clip">{row.subject}</td>
                      <td className="num">{days(row.lastFromClientAt, data.now)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
        </div>

        <section className="card" aria-labelledby="stage-title">
          <div className="card__head">
            <h2 id="stage-title" className="section-title">Time in stage</h2>
            <span className="card__meta">Against the median of the last 12 months</span>
          </div>
          <table className="table">
            <thead>
              <tr>
                <th scope="col">Deal</th>
                <th scope="col">Stage</th>
                <th scope="col">Owner</th>
                <th scope="col" className="num">Days in stage</th>
                <th scope="col" className="num">Median</th>
                <th scope="col">Against median</th>
              </tr>
            </thead>
            <tbody>
              {views.inStage.map(({ deal, days: inStage, median }) => (
                <tr key={deal.id}>
                  <td><span className="cell-title">{deal.codeName}</span></td>
                  <td>{deal.stage}</td>
                  <td>{byId(data.users, deal.ownerId)?.name}</td>
                  <td className="num">{inStage}</td>
                  <td className="num">{median}</td>
                  <td>{median && inStage > median ? <span className="overdue"><span className="overdue__dot" aria-hidden="true">!</span>{inStage - median} days over</span> : <span className="muted">Within median</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        <div className="opt-grid">
          <section className="card" aria-labelledby="reply-title">
            <div className="card__head">
              <h2 id="reply-title" className="section-title">Reply rate by template and sector</h2>
              <span className="card__meta">Last 90 days</span>
            </div>
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">Template</th>
                  <th scope="col">Sector</th>
                  <th scope="col" className="num">Sent</th>
                  <th scope="col" className="num">Replied</th>
                  <th scope="col" className="num">Reply rate</th>
                </tr>
              </thead>
              <tbody>
                {data.replyStats.map((row) => (
                  <tr key={`${row.template}-${row.sector}`}>
                    <td>{row.template}</td>
                    <td>{row.sector}</td>
                    <td className="num">{row.sent}</td>
                    <td className="num">{row.replied}</td>
                    <td className="num">{percent(row.replied, row.sent)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          <section className="card" aria-labelledby="conversion-title">
            <div className="card__head">
              <h2 id="conversion-title" className="section-title">Conversion per stage</h2>
              <span className="card__meta">Last 12 months</span>
            </div>
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">Stage</th>
                  <th scope="col" className="num">Reached</th>
                  <th scope="col" className="num">Moved on</th>
                  <th scope="col" className="num">Conversion</th>
                </tr>
              </thead>
              <tbody>
                {data.conversion.map((row) => (
                  <tr key={row.stage}>
                    <td>
                      {row.stage} <span className="muted">to {STAGES[STAGES.indexOf(row.stage as (typeof STAGES)[number]) + 1]}</span>
                    </td>
                    <td className="num">{row.reached}</td>
                    <td className="num">{row.advanced}</td>
                    <td className="num">{percent(row.advanced, row.reached)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </div>

        <section className="card" aria-labelledby="bottleneck-title">
          <div className="card__head">
            <h2 id="bottleneck-title" className="section-title">Bottlenecks</h2>
            <span className="card__meta">Log one from any page with "Log bottleneck" in the menu</span>
          </div>
          {data.bottlenecks.length === 0 ? (
            <EmptyState>No bottleneck logged yet.</EmptyState>
          ) : (
            <ul className="row-list">
              {data.bottlenecks.map((row) => (
                <li key={row.id} className="bottleneck">
                  <div>
                    <p className="bottleneck__what">{row.what}</p>
                    <p className="cell-sub">
                      {byId(data.users, row.byId)?.name}, {formatWhen(row.at, data.now)}. {row.where}
                      {row.dealId && `, ${byId(data.deals, row.dealId)?.codeName}`}
                    </p>
                  </div>
                  {row.promoted ? (
                    <span className="chip chip--done">In Notion</span>
                  ) : (
                    <button type="button" className="button button--small button--quiet button--row" onClick={() => act({ intent: "promote", id: row.id }, "Notion issue created.")}>
                      Make Notion issue
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </>
  );
}
