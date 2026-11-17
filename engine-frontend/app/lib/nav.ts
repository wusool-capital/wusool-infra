// The 13 tabs in 5 groups, from the PRD navigation diagram.
// One list feeds the left nav and the bottleneck form's "Where" field.

import { isLive } from "./data-mode";
import {
  BookOpen, Briefcase, Calculator, FileText, Gauge, Handshake, House, Kanban, MagnifyingGlass, Newspaper, PaperPlaneTilt, Storefront, Target,
  type Icon,
} from "@phosphor-icons/react";

export type NavItem = {
  label: string;
  path: string;
  title: string;
  summary: string;
  icon: Icon;
  external?: boolean;
  /** Has a backend. In live mode every other page is demo data, so its link is greyed out. */
  live?: boolean;
  /** Other paths that keep this item highlighted, such as a deal page under Pipeline. */
  alsoActiveOn?: string[];
};

export type NavGroup = { label: string; items: NavItem[] };

export const GITBOOK_URL = "https://wusool-capital.gitbook.io/docs";
// Reports are written and published in Sanity, which already runs the website (decided 9 Nov 2026).
// Placeholder until the direct Studio address is known: the manage page lists the projects.
export const SANITY_STUDIO_URL = "https://www.sanity.io/manage";

export const navGroups: NavGroup[] = [
  {
    label: "Work",
    items: [
      { label: "Home", icon: House, path: "/", title: "Home", summary: "To-dos, action emails, items to review, meetings, data room activity and the live feed." },
      { label: "Pipeline", icon: Kanban, path: "/pipeline", title: "Pipeline", summary: "Every deal as a kanban or a list. A card opens a quick view; Open deal goes to the deal page.", alsoActiveOn: ["/deals"] },
      { label: "Outreach", icon: PaperPlaneTilt, path: "/outreach", title: "Outreach", summary: "Every counterparty across your deals and lists: last contact, follow-ups, next step, send." },
    ],
  },
  {
    label: "Lists",
    items: [
      { label: "Buyers", icon: Briefcase, path: "/buyers/universe", title: "Buyers universe", summary: "All buyer roles in Attio, with filters and a record drawer.", live: true },
      { label: "Sellers", icon: Storefront, path: "/sellers/universe", title: "Sellers universe", summary: "All seller roles in Attio, with filters and a record drawer.", live: true },
      { label: "Search", icon: MagnifyingGlass, path: "/search/buyers", title: "Search", summary: "Find new buyers or sellers, enrich them, and add them to Attio, a deal or the pipeline.", alsoActiveOn: ["/search"] },
    ],
  },
  {
    label: "Firm",
    items: [
      { label: "Multiples", icon: Calculator, path: "/multiples", title: "Multiples", summary: "Valuation multiples from the comparables database, with web search as a fallback." },
      { label: "Scorecards", icon: Target, path: "/scorecards", title: "Scorecards", summary: "Weekly scorecards with history and averages. Add people and companies met." },
      { label: "Referral partners", icon: Handshake, path: "/partners", title: "Referral partners", summary: "Partners, terms and referral links, and the leads each partner referred." },
      { label: "Engine optimization", icon: Gauge, path: "/optimization", title: "Engine optimization", summary: "Bottlenecks, drop-offs, and which outreach works and which does not." },
      { label: "Reports", icon: Newspaper, path: SANITY_STUDIO_URL, title: "Reports", summary: "Insights and reports, written and published in Sanity.", external: true },
    ],
  },
  {
    label: "Settings",
    items: [
      { label: "Skills", icon: FileText, path: "/settings/skills", title: "Skills", summary: "Contract, proposal, NDA, email, invoice, teaser and CIM skills, with version and where each is used." },
      { label: "GitBook", icon: BookOpen, path: GITBOOK_URL, title: "GitBook", summary: "Technical docs, admins only.", external: true },
    ],
  },
];

export const navItems = navGroups.flatMap((group) => group.items);

/** Where sign-in lands: Home is demo data, so live mode opens the Buyers page. */
export const START_PATH = isLive ? "/buyers/universe" : "/";

/** Demo mode offers every page; live mode only those with a backend (and links out of the app). */
export const isAvailable = (item: NavItem) => !isLive || item.live === true || item.external === true;
