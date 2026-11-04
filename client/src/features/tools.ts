// The Slack toolkit's commands; only find-match runs on the web so far.
export interface Tool {
  id: string;
  name: string;
  description: string;
  slackCommand: string;
  web: boolean;
}

export const TOOLS: Tool[] = [
  {
    id: "find-match",
    name: "Find match",
    description:
      "Score the CRM's sellers against a buyer's mandate and review a reasoned shortlist.",
    slackCommand: "/find-match",
    web: true,
  },
  {
    id: "check-buyer",
    name: "Check buyer",
    description:
      "List what's missing from a buyer's profile and where it conflicts with your notes.",
    slackCommand: "/check-buyer",
    web: false,
  },
  {
    id: "enrich-seller",
    name: "Enrich seller",
    description: "Research a seller and propose profile updates for review.",
    slackCommand: "/enrich-seller",
    web: false,
  },
  {
    id: "enrich-buyer",
    name: "Enrich buyer",
    description: "Research a buyer and propose profile updates for review.",
    slackCommand: "/enrich-buyer",
    web: false,
  },
  {
    id: "add-seller",
    name: "Add seller",
    description:
      "Create a seller in Attio and the CRM after a duplicate check.",
    slackCommand: "/add-seller",
    web: false,
  },
  {
    id: "edit-buyer",
    name: "Edit buyer",
    description:
      "Update a buyer's mandate: vertical, geography, ticket size and EBITDA.",
    slackCommand: "/edit-buyer",
    web: false,
  },
];
