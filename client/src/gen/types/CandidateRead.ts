// @ts-nocheck

import type { CriterionRead } from './CriterionRead'
import type { ResearchRead } from './ResearchRead'
import type { SellerProfileRead } from './SellerProfileRead'

export const candidateReadOriginEnum = {
  crm: 'crm',
  discovery: 'discovery',
} as const;

export type CandidateReadOriginEnumKey = (typeof candidateReadOriginEnum)[keyof typeof candidateReadOriginEnum];

export type CandidateRead = {
  criteria: CriterionRead[];
  data_confidence: number | null;
  deal_attio_id: string | null;
  decided_at: string | null;
  decision: string | null;
  /**
   * @description
   * Format: `uuid`
   * @type string
   */
  id: string;
  match_score: number | null;
  origin: CandidateReadOriginEnumKey;
  profile: SellerProfileRead | null;
  rank: number;
  recommended_pitch: string | null;
  research: ResearchRead | null;
  risks_and_gaps: string | null;
  seller_attio_id: string | null;
  seller_org_name: string;
  source_url: string | null;
  status: string;
  why_chosen_over_alternatives: string | null;
  why_it_matches: string | null;
};
