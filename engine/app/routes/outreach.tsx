import { CaretDown, CaretRight } from "@phosphor-icons/react";
import { useSearchParams } from "react-router";
import { OutreachDrawer } from "../components/outreach/outreach-drawer";
import { EmptyState } from "../components/ui/empty-state";
import { OverdueMark } from "../components/ui/overdue-mark";
import { CURRENT_USER_ID, enrichCounterparty, getOutreach, sendOutreach } from "../demo/api";
import { byId } from "../lib/by-id";
import { dayKey, formatDate } from "../lib/format";
import { GROUP_TITLES, OUTREACH_GROUPS, outreachState, type OutreachGroup, type OutreachState } from "../lib/outreach-state";
import type { Route } from "./+types/outreach";
import { Segmented } from "../components/ui/segmented";

export async function clientLoader() {
  return getOutreach(CURRENT_USER_ID);
}

export async function clientAction({ request }: Route.ClientActionArgs) {
  const form = await request.formData();
  const field = (name: string) => String(form.get(name) ?? "");
  switch (field("intent")) {
    case "outreach":
      return sendOutreach(field("id"), field("contactId"), field("template"), field("link"), field("summary"));
    case "enrich":
      return enrichCounterparty(field("id"));
  }
}

// Two kinds of outreach (decided 7 Nov 2026): buyers or targets on the deals you run, and
// owners you ask whether they would sell, before any mandate exists.
const KINDS = [
  { id: "all", label: "All" },
  { id: "deals", label: "Buyers on my deals" },
  { id: "owners", label: "Owners to approach" },
] as const;
type Kind = (typeof KINDS)[number]["id"];

const DEFAULT_CLOSED: string[] = ["replied", "no-reply"];

export default function Outreach({ loaderData: data }: Route.ComponentProps) {
  const [params, setParams] = useSearchParams();
  const kind = (KINDS.some((option) => option.id === params.get("kind")) ? params.get("kind") : "all") as Kind;
  const today = dayKey(data.now);

  const rows = data.rows
    .filter((row) => kind === "all" || (kind === "owners" ? Boolean(row.listName) : !row.listName))
    .map((row) => ({ row, state: outreachState(row, today) }));
  const inGroup = (group: OutreachGroup) => rows.filter(({ state }) => state.group === group).sort((a, b) => a.state.order.localeCompare(b.state.order));

  const set = (key: string, value: string | null) =>
    setParams(
      (next) => {
        if (value) next.set(key, value);
        else next.delete(key);
        return next;
      },
      { preventScrollReset: true },
    );
  const open = (id: string) => set("row", id);
  const openRow = byId(data.rows, params.get("row") ?? undefined);
  const shownGroups = OUTREACH_GROUPS.filter((group) => inGroup(group).length > 0);
  // Groups to act on start open; finished ones start closed. The choice lives in the URL ("none" = all open),
  // so the page comes back as it was left.
  const closed = params.has("closed") ? (params.get("closed") ?? "").split(",") : DEFAULT_CLOSED;
  const toggle = (group: OutreachGroup) => {
    const next = closed.includes(group) ? closed.filter((item) => item !== group) : [...closed, group];
    set("closed", next.filter((item) => item !== "none").join(",") || "none");
  };

  return (
    <>
      <h1 className="page-title">Outreach</h1>
      <div className="toolbar">
        <Segmented role="group" aria-label="Who">
          {KINDS.map((option) => (
            <button key={option.id} type="button" className="segmented__option" aria-pressed={kind === option.id} onClick={() => set("kind", option.id === "all" ? null : option.id)}>
              {option.label}
            </button>
          ))}
        </Segmented>
      </div>

      <div className="page-body">
        {shownGroups.length === 0 ? (
          <EmptyState>No one to contact yet.</EmptyState>
        ) : (
          <div className="card card--flush">
            <table className="table table--fixed outreach-table">
              <colgroup>
                <col style={{ width: "17%" }} />
                <col style={{ width: "13%" }} />
                <col style={{ width: "12%" }} />
                <col style={{ width: "26%" }} />
                <col />
                <col style={{ width: "144px" }} />
              </colgroup>
              <thead>
                <tr>
                  <th scope="col">Company</th>
                  <th scope="col">Deal or list</th>
                  <th scope="col">Contact</th>
                  <th scope="col">Status</th>
                  <th scope="col">Last message</th>
                  <th scope="col">
                    <span className="visually-hidden">Action</span>
                  </th>
                </tr>
              </thead>
              {shownGroups.map((group) => (
                <tbody key={group}>
                  <tr className="group-row">
                    <th scope="colgroup" colSpan={6}>
                      <button type="button" className="group-row__toggle" aria-expanded={!closed.includes(group)} onClick={() => toggle(group)}>
                        {closed.includes(group) ? <CaretRight size={12} weight="bold" aria-hidden="true" /> : <CaretDown size={12} weight="bold" aria-hidden="true" />}
                        {GROUP_TITLES[group]} <span className="group-row__count">{inGroup(group).length}</span>
                      </button>
                    </th>
                  </tr>
                  {!closed.includes(group) && inGroup(group).map(({ row, state }) => (
                    <tr key={row.id} className="row-clickable" tabIndex={0} onClick={() => open(row.id)} onKeyDown={(event) => event.key === "Enter" && open(row.id)}>
                      <td>
                        <span className="cell-title cell-clip">{row.name}</span>
                      </td>
                      <td className="cell-clip">{byId(data.deals, row.dealId || undefined)?.codeName ?? row.listName}</td>
                      <td className="cell-clip">{byId(data.people, row.contactIds[0])?.name ?? <span className="muted">Not found yet</span>}</td>
                      <td>
                        <StatusCell state={state} />
                      </td>
                      <td className="cell-clip" title={row.outreach?.lastMessage}>
                        {row.outreach?.lastMessage ?? <span className="muted">Nothing sent yet</span>}
                      </td>
                      <td>
                        <button
                          type="button"
                          className={`button button--small button--row ${state.group === "due" ? "" : "button--quiet"}`}
                          onClick={(event) => {
                            event.stopPropagation();
                            open(row.id);
                          }}
                        >
                          {actionLabel(state)}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              ))}
            </table>
          </div>
        )}
      </div>
      {openRow && <OutreachDrawer key={openRow.id} row={openRow} data={data} onClose={() => set("row", null)} />}
    </>
  );
}

function StatusCell({ state }: { state: OutreachState }) {
  switch (state.group) {
    case "due":
      return (
        <span className="follow-up-line">
          {state.overdue && <OverdueMark />}
          <span className="cell-clip">
            {state.step}
            {state.date && (state.overdue ? `, ${formatDate(state.date)}` : ", today")}
          </span>
        </span>
      );
    case "waiting":
      return (
        <span className="cell-clip">
          {state.step} on {formatDate(state.date!)}
        </span>
      );
    case "replied":
      return <span>Replied {formatDate(state.date!)}</span>;
    case "no-contact":
      return <span className="muted">Find a contact to start</span>;
    case "no-reply":
      return <span className="muted">Decide whether to keep this name</span>;
  }
}

function actionLabel(state: OutreachState) {
  if (state.group === "due") return state.step === "First message" ? "Write message" : "Follow up";
  if (state.group === "no-contact") return "Find contact";
  return "Open";
}
