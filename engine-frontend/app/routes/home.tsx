import { redirect, useSearchParams } from "react-router";
import { ActionEmails } from "../components/home/action-emails";
import { Agenda } from "../components/home/agenda";
import { EmailDrawer } from "../components/home/email-drawer";
import { MorningBrief } from "../components/home/morning-brief";
import { PendingDrawer } from "../components/home/pending-drawer";
import { PendingReview } from "../components/home/pending-review";
import { HomeCell } from "../components/home/home-cell";
import { ToolTabCheck } from "../components/home/tool-tab-check";
import { Workstreams } from "../components/home/workstreams";
import {
  CURRENT_USER_ID,
  approvePendingItem,
  getHome,
  markNotActionable,
  rejectPendingItem,
  saveToolTabAnswer,
  sendReply,
  updateWorkstream,
  deleteWorkstream,
} from "../demo/api";
import type { WorkstreamStatus } from "../demo/types";
import { byId } from "../lib/by-id";
import { START_PATH } from "../lib/nav";
import { formatLongDate } from "../lib/format";
import type { Route } from "./+types/home";

// Home is the only tab with a phone layout (PRD: phone covers triage, tasks and approvals).
export const handle = { phone: true };

export async function clientLoader() {
  // Home is demo data; live mode opens on the Buyers page instead.
  if (START_PATH !== "/") throw redirect(START_PATH);
  return getHome(CURRENT_USER_ID);
}

export async function clientAction({ request }: Route.ClientActionArgs) {
  const form = await request.formData();
  const field = (name: string) => String(form.get(name) ?? "");

  switch (field("intent")) {
    case "pending-approve":
      return approvePendingItem(CURRENT_USER_ID, field("id"), JSON.parse(field("edit")));
    case "pending-reject":
      return rejectPendingItem(field("id"));
    case "email-send":
      return sendReply(field("id"));
    case "email-dismiss":
      return markNotActionable(field("id"));
    case "workstream-status":
      return updateWorkstream(field("id"), { status: field("status") as WorkstreamStatus });
    case "workstream-next-step":
      return updateWorkstream(field("id"), { nextStep: field("nextStep") });
    case "workstream-name":
      return updateWorkstream(field("id"), { name: field("name") });
    case "workstream-delete":
      return deleteWorkstream(field("id"));
    case "workstream-due":
      return updateWorkstream(field("id"), { dueDate: field("dueDate") });
    case "tool-tab":
      return saveToolTabAnswer(CURRENT_USER_ID, JSON.parse(field("tools")));
  }
}

export default function Home({ loaderData: data }: Route.ComponentProps) {
  const [params, setParams] = useSearchParams();
  const openEmail = byId(data.emails, params.get("email") ?? undefined);
  const openReview = byId(data.pendingItems, params.get("review") ?? undefined);

  const closeDrawer = () =>
    setParams(
      (next) => {
        next.delete("email");
        next.delete("review");
        next.delete("generate");
        return next;
      },
      { preventScrollReset: true },
    );

  // Emails to send (drafts and follow-ups) sit with the emails to answer; Approvals holds only record changes.
  const isEmail = (item: (typeof data.pendingItems)[number]) => item.kind === "email" || item.kind === "follow-up";
  const emailsToSend = data.pendingItems.filter(isEmail);
  const recordChanges = data.pendingItems.filter((item) => !isEmail(item));

  // The end of day question shows from 17:00 Dubai, when the day's tool use is known (PRD H10).
  const showToolCheck = new Date(data.now).getUTCHours() + 4 >= 17;

  return (
    <>
      <div className="home-head">
        <h1 className="page-title">Home</h1>
        <p className="home-head__date">{formatLongDate(data.now)}</p>
      </div>

      <div className="home-grid">
        <HomeCell id="day" title="Your day" className="home__desktop-only">
          <MorningBrief brief={data.brief} />
          <Agenda items={data.agenda} deals={data.deals} people={data.people} now={data.now} />
          {showToolCheck && <ToolTabCheck answer={data.toolTabAnswer} />}
        </HomeCell>

        {/* Everything to act on, in one full-height column beside the day. */}
        <HomeCell
          id="actions"
          title="Actions"
          tabs={[
            {
              id: "emails",
              label: "Emails",
              count: data.emails.length + emailsToSend.length,
              content: (
                <>
                  <ActionEmails emails={data.emails} deals={data.deals} people={data.people} now={data.now} />
                  {emailsToSend.length > 0 && <PendingReview title="To send" items={emailsToSend} deals={data.deals} people={data.people} />}
                </>
              ),
            },
            { id: "approvals", label: "Approvals", count: recordChanges.length, content: <PendingReview items={recordChanges} deals={data.deals} people={data.people} /> },
            { id: "workstreams", label: "Workstreams", count: data.workstreams.length, desktopOnly: true, content: <Workstreams workstreams={data.workstreams} /> },
          ]}
        />

      </div>

      {openEmail && <EmailDrawer key={openEmail.id} email={openEmail} deals={data.deals} people={data.people} onClose={closeDrawer} />}
      {openReview && <PendingDrawer key={openReview.id} item={openReview} generated={params.get("generate") === "1"} deals={data.deals} people={data.people} onClose={closeDrawer} />}
    </>
  );
}

