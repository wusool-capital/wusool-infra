// @ts-nocheck

import type { BuyerCandidateOrg } from './BuyerCandidateOrg'

export type BuyerSummary = {
  id: string;
  mandate_status?: string | null;
  model?: string | null;
  organization: BuyerCandidateOrg;
  target_vertical?: string | null;
};
