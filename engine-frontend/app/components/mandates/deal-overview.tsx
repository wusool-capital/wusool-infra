import { Link } from "react-router";
import type { DealViewData } from "../../demo/types";
import { byId } from "../../lib/by-id";
import { formatMoney } from "../../lib/format";
import { STAGES, daysPerStage } from "../../lib/stages";
import { usePanel } from "./use-deal";

// Overview panel (PRD MV1, MV2, MV4), fixed above the tabs and kept compact so the tab content gets
// the height: identity and buttons on one row, the figures on one line, then the stage bars.
// No scroll motion (Jules, 8 Nov 2026). No fees here.
export function DealOverview({ data }: { data: DealViewData }) {
  const { deal } = data;
  return (
    <section className="card deal-overview" aria-labelledby="deal-title">
      <DealHead data={data} />
      {deal.status !== "Active" && <p className="side-banner">Mandate {deal.status.toLowerCase()}.</p>}
      <Figures data={data} />
      <StageTracker current={deal.stage} enteredAt={data.details.stageEnteredAt} now={data.now} />
    </section>
  );
}

function DealHead({ data }: { data: DealViewData }) {
  const { deal } = data;
  const { openPanel } = usePanel();
  const owner = byId(data.users, deal.ownerId);
  return (
    <div className="deal-overview__head">
      <div className="deal-overview__id">
        <h1 id="deal-title" className="page-title deal-overview__title">
          {deal.codeName}
        </h1>
        <span className="badge">{deal.side === "sell" ? "Sell-side" : "Buy-side"}</span>
        <span>{deal.clientName}</span>
        <span className="muted">Lead advisor: {owner?.name}</span>
      </div>
      <div className="button-row">
        <button type="button" className="button button--quiet" onClick={() => openPanel("edit")}>
          Edit
        </button>
        <button type="button" className="button button--quiet" onClick={() => openPanel("email-client")}>
          Email client
        </button>
      </div>
    </div>
  );
}

// Days in each stage sit in brackets after its name, so a stalled deal shows at a glance.
function StageTracker({ current, enteredAt, now }: { current: DealViewData["deal"]["stage"]; enteredAt: DealViewData["details"]["stageEnteredAt"]; now: string }) {
  const currentIndex = STAGES.indexOf(current);
  const days = daysPerStage(enteredAt, current, now);
  return (
    <ol className="stage-bars" aria-label="Deal stage">
      {STAGES.map((stage, index) => {
        const state = index < currentIndex ? "done" : index === currentIndex ? "current" : "upcoming";
        return (
          <li key={stage} className={`stage-bars__step stage-bars__step--${state}`} aria-current={state === "current" ? "step" : undefined}>
            <span className="stage-bars__bar" aria-hidden="true" />
            <span className="stage-bars__name">
              {stage}
              {days[stage] !== undefined && <span className="stage-bars__days"> ({days[stage]})</span>}
              <span className="visually-hidden">{days[stage] !== undefined && ` days in stage: ${days[stage]}`}</span>
              <span className="visually-hidden">{state === "done" ? ", completed" : state === "current" ? ", current stage" : ", not started"}</span>
            </span>
          </li>
        );
      })}
    </ol>
  );
}

// MV4: figures from the last financial year; the multiple is computed here, never by AI.
function Figures({ data }: { data: DealViewData }) {
  const { fy, revenueUsd, grossProfitUsd, ebitdaUsd, askingPriceUsd } = data.details.financials;
  const margin = (value?: number) => (value !== undefined && revenueUsd ? `${Math.round((value / revenueUsd) * 100)}%` : null);
  const multiple = askingPriceUsd && ebitdaUsd ? `${(askingPriceUsd / ebitdaUsd).toFixed(1)}x EBITDA` : null;

  const figures = [
    { label: `Revenue ${fy}`, value: revenueUsd, extra: null },
    { label: "Gross profit", value: grossProfitUsd, extra: margin(grossProfitUsd) },
    { label: "EBITDA", value: ebitdaUsd, extra: margin(ebitdaUsd) },
    { label: "Asking price", value: askingPriceUsd, extra: multiple },
  ];

  // PRD MU6: comparables for this deal's sector and size (half to double its value).
  const value = data.deal.valueUsd;
  const multiplesLink = `/multiples?sector=${encodeURIComponent(data.deal.sector)}${value ? `&size=${value / 2_000_000}-${(value * 2) / 1_000_000}` : ""}&searched=1`;

  return (
    <div className="figure-line">
      <dl className="figure-line__list">
        {figures.map((figure) => (
          <div key={figure.label} className="figure-line__item">
            <dt>{figure.label}</dt>
            <dd>
              {figure.value === undefined ? (
                <span className="muted">Not set</span>
              ) : (
                <>
                  <span className="figure-line__value">{formatMoney(figure.value)}</span>
                  {figure.extra && <span className="muted">{figure.extra}</span>}
                </>
              )}
            </dd>
          </div>
        ))}
      </dl>
      <Link to={multiplesLink}>See multiples</Link>
    </div>
  );
}
