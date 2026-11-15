import { Check } from "@phosphor-icons/react";
import { useState } from "react";
import type { DealViewData, Material, MaterialItem } from "../../demo/types";
import { byId } from "../../lib/by-id";
import { formatMoney } from "../../lib/format";
import { Drawer } from "../ui/drawer";
import { EngagementPanel } from "./engagement-panel";
import { inHand, inSentence, isAgreement, missingFromClient, nextMove } from "./materials";
import { useDealAction, usePanel } from "./use-deal";

// PRD MM3 to MM5 in one panel: the checklist (client items and ours), the email asking the client
// for what is missing, the prompt that opens Claude with the right skill, and terms for agreements.
export function MaterialDrawer({ material, data, onClose }: { material: Material; data: DealViewData; onClose: () => void }) {
  const act = useDealAction();
  const { openPanel } = usePanel();
  const missing = missingFromClient(material);
  const client = data.deal.contactIds.map((id) => byId(data.people, id)).find((person) => person?.role === "client");
  const owner = byId(data.users, data.deal.ownerId);
  const draft = missing.length
    ? `Dear ${client?.name.split(" ")[0] ?? ""},\n\nFor the ${inSentence(material.name)}, could you share:\n${missing.map((item) => `- ${item.name}: ${item.why}`).join("\n")}\n\nYou can drop them in the shared Drive folder or reply with attachments.\n\nBest regards,\n${owner?.name ?? ""}`
    : "";
  const [body, setBody] = useState(draft);
  const move = nextMove(material);
  const canSendCim = material.name === "CIM" && material.status === "Approved" && data.deal.side === "sell";
  const ourGaps = material.items.filter((item) => !item.have && item.from === "us");
  const [drafting, setDrafting] = useState(false);
  const canDraftContract = material.name === "Engagement contract" && material.status !== "Signed";

  // The engagement letter (terms from the skills, worked fee examples, send) replaces this panel's
  // content instead of opening a second layer; Back returns to the checklist.
  if (drafting) return <EngagementPanel deal={data.deal} people={data.people} now={data.now} onBack={() => setDrafting(false)} onClose={onClose} />;

  return (
    <Drawer
      title={material.name}
      status={`${inHand(material)} of ${material.items.length} in hand. ${material.status}.`}
      dirty={body !== draft}
      onClose={onClose}
      actions={
        <>
          {missing.length > 0 && (
            <button
              type="button"
              className="button"
              disabled={!client || !body.trim()}
              onClick={() => {
                act({ intent: "request-docs", items: JSON.stringify(missing.map((item) => item.name)) }, `Request sent to ${client?.name}. Demo: nothing was sent.`);
                onClose();
              }}
            >
              Send request
            </button>
          )}
          {canSendCim && (
            <button type="button" className="button" onClick={() => openPanel("send-cim")}>
              Send to signed buyers
            </button>
          )}
          {canDraftContract && (
            <button type="button" className={missing.length ? "button button--quiet" : "button"} onClick={() => setDrafting(true)}>
              Draft contract
            </button>
          )}
          {move && (
            <button
              type="button"
              className={missing.length || canSendCim || canDraftContract ? "button button--quiet" : "button"}
              onClick={() => act({ intent: "material-status", id: material.id, status: move.status }, `${material.name}: ${move.status.toLowerCase()}.`)}
            >
              {move.label}
            </button>
          )}
        </>
      }
    >
      <section className="drawer__section">
        <Checklist title="From the client" items={material.items.filter((item) => item.from === "client")} />
        <Checklist title="From us" items={material.items.filter((item) => item.from === "us")} />
      </section>

      {missing.length > 0 && (
        <section className="drawer__section">
          <div className="drawer__section-head">
            <h3 className="panel-heading">Email to {client?.name ?? "the client"}</h3>
            <span className="badge">AI draft</span>
          </div>
          <div className="field">
            <label htmlFor="req-body">Message</label>
            <textarea id="req-body" rows={9} value={body} onChange={(event) => setBody(event.target.value)} />
          </div>
        </section>
      )}

      {material.name !== "Data room" && <ClaudeSection material={material} data={data} blocked={missing.length + ourGaps.length} />}
      {isAgreement(material) && <Terms material={material} />}
    </Drawer>
  );
}

function Checklist({ title, items }: { title: string; items: MaterialItem[] }) {
  if (items.length === 0) return null;
  return (
    <div className="material-checklist">
      <h3 className="panel-heading">
        {title} <span className="muted">{items.filter((item) => item.have).length} of {items.length}</span>
      </h3>
      <ul className="checklist">
        {items.map((item) => (
          <li key={item.name} className="checklist__item">
            <span className={item.have ? "checklist__mark checklist__mark--done" : "checklist__mark"} aria-hidden="true">
              {item.have && <Check size={11} weight="bold" />}
            </span>
            <span className="checklist__text">
              <span className="checklist__name">
                {item.name} <span className={item.have ? "muted" : "checklist__missing"}>{item.have ? "In hand" : "Missing"}</span>
              </span>
              <span className="cell-sub">{item.why}</span>
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

// PRD MM4: Claude cannot open an Engine link, so the prompt carries the deal as text. It names the
// skill and uses the code name only, so nothing confidential leaves in the link.
function ClaudeSection({ material, data, blocked }: { material: Material; data: DealViewData; blocked: number }) {
  const [copied, setCopied] = useState(false);
  const { deal, details } = data;
  const prompt = [
    material.skill ? `Use the ${material.skill} skill to draft the ${inSentence(material.name)} for ${deal.codeName}.` : `Draft the ${inSentence(material.name)} for ${deal.codeName}.`,
    `${deal.side === "sell" ? "Sell-side" : "Buy-side"}, ${deal.sector}, ${deal.city}.`,
    details.financials.revenueUsd ? `${details.financials.fy}: revenue ${formatMoney(details.financials.revenueUsd)}, EBITDA ${formatMoney(details.financials.ebitdaUsd ?? 0)}.` : "",
    `Inputs are in the Drive folder "${deal.codeName}": ${material.items.map((item) => item.name.toLowerCase()).join("; ")}.`,
    "Use the code name only; never the client's real name.",
  ]
    .filter(Boolean)
    .join("\n");

  return (
    <section className="drawer__section">
      <h3 className="panel-heading">Draft in Claude</h3>
      {blocked > 0 ? (
        <p className="muted">
          {blocked} {blocked === 1 ? "item is" : "items are"} missing. Open in Claude appears once the checklist is complete.
        </p>
      ) : (
        <>
          <p className="muted">
            Opens Claude with this prompt. Attach {material.skill ? `the ${material.skill} skill and ` : ""}the deal folder there.
          </p>
          <pre className="prompt-box">{prompt}</pre>
          <div className="button-row">
            <a className="button button--small" href={`https://claude.ai/new?q=${encodeURIComponent(prompt)}`} target="_blank" rel="noreferrer">
              Open in Claude<span className="visually-hidden"> (opens in a new tab)</span>
            </a>
            <button
              type="button"
              className="button button--small button--quiet"
              onClick={() => {
                navigator.clipboard?.writeText(prompt).catch(() => {});
                setCopied(true);
              }}
            >
              Copy prompt
            </button>
            {copied && <span className="muted" role="status">Prompt copied</span>}
          </div>
        </>
      )}
    </section>
  );
}

// PRD MM5: fee terms stay hidden until Show terms, so the page is safe to screen-share.
function Terms({ material }: { material: Material }) {
  const [showTerms, setShowTerms] = useState(false);
  return (
    <section className="drawer__section">
      <h3 className="panel-heading">Main terms</h3>
      {material.mainTerms.length ? (
        <ul className="brief-list">
          {material.mainTerms.map((term) => (
            <li key={term}>{term}</li>
          ))}
        </ul>
      ) : (
        <p className="muted">Not drafted yet.</p>
      )}
      {material.feeTerms.length > 0 && (
        <>
          <div className="drawer__section-head material-terms__fees">
            <h3 className="panel-heading">Fee terms</h3>
            <button type="button" className="text-button" aria-expanded={showTerms} onClick={() => setShowTerms(!showTerms)}>
              {showTerms ? "Hide terms" : "Show terms"}
            </button>
          </div>
          {showTerms && (
            <ul className="brief-list">
              {material.feeTerms.map((term) => (
                <li key={term}>{term}</li>
              ))}
            </ul>
          )}
        </>
      )}
    </section>
  );
}
