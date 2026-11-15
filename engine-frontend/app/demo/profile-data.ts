// Demo profile and connections for the signed-in advisor. Once live, statuses come from each
// integration's token check (Google, Attio, Slack, Apollo, Notion, VantageKit, WhatsApp Business).
import type { Connection, Profile } from "./types";

export const profile: Profile = {
  fullName: "Jules Chasles",
  title: "Co-founder and COO",
  email: "jules@wusoolcapital.com",
  whatsapp: "+971 50 000 0000",
  admin: true,
};

export const connections: Connection[] = [
  { id: "gmail", name: "Gmail", purpose: "Action emails, replies and sending after your click", account: "jules@wusoolcapital.com", status: "Connected", lastSyncAt: "2026-11-11T08:38:00+04:00" },
  { id: "calendar", name: "Google Calendar", purpose: "Agenda, prep cards and people met suggestions", account: "jules@wusoolcapital.com", status: "Connected", lastSyncAt: "2026-11-11T08:35:00+04:00" },
  { id: "drive", name: "Google Drive", purpose: "Deal folders, engagement letters and materials", account: "jules@wusoolcapital.com", status: "Connected", lastSyncAt: "2026-11-11T08:10:00+04:00" },
  { id: "attio", name: "Attio", purpose: "Deals, people, buyer and seller roles, scorecards", account: "Wusool Capital workspace", status: "Connected", lastSyncAt: "2026-11-11T08:39:00+04:00" },
  { id: "slack", name: "Slack", purpose: "Urgent alerts and the 07:30 brief", account: "wusool-capital.slack.com", status: "Needs attention", lastSyncAt: "2026-11-08T07:30:00+04:00", issue: "Token expired on 8 Nov 2026. Alerts are paused." },
  { id: "apollo", name: "Apollo", purpose: "Contact enrichment and company search", account: "Team plan, 340 credits left", status: "Connected", lastSyncAt: "2026-11-11T07:55:00+04:00" },
  { id: "notion", name: "Notion", purpose: "Workstreams, rocks and issues", account: "Wusool HQ", status: "Connected", lastSyncAt: "2026-11-11T08:00:00+04:00" },
  { id: "vantagekit", name: "VantageKit", purpose: "Data room views and downloads", account: "wusool.vantagekit.example", status: "Needs attention", lastSyncAt: "2026-11-10T22:00:00+04:00", issue: "Last sync failed: rate limit. Retrying every hour." },
  { id: "whatsapp", name: "WhatsApp Business", purpose: "Client messages logged to the deal history", account: "", status: "Not connected" },
];

/** Integrations that can be added from "Add connector". */
export const availableConnectors: Pick<Connection, "id" | "name" | "purpose">[] = [
  { id: "granola", name: "Granola", purpose: "Meeting notes and action items into the deal history" },
  { id: "sanity", name: "Sanity", purpose: "Partner pages on the website (admins)" },
  { id: "outlook", name: "Microsoft Outlook", purpose: "For clients who share files through Microsoft 365" },
];
