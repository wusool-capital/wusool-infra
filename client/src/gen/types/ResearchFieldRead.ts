// @ts-nocheck

export const researchFieldReadTargetEnum = {
  organization: 'organization',
  seller_role: 'seller_role',
} as const;

export type ResearchFieldReadTargetEnumKey = (typeof researchFieldReadTargetEnum)[keyof typeof researchFieldReadTargetEnum];

export type ResearchFieldRead = {
  confidence: number;
  display: string;
  name: string;
  rationale: string;
  saved: boolean;
  source_url: string;
  target: ResearchFieldReadTargetEnumKey;
};
