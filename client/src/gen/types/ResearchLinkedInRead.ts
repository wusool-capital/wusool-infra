// @ts-nocheck

import type { ResearchJobChangeRead } from './ResearchJobChangeRead'
import type { ResearchPostRead } from './ResearchPostRead'

export const researchLinkedInReadOutcomeEnum = {
  completed: 'completed',
  skipped: 'skipped',
  failed: 'failed',
} as const;

export type ResearchLinkedInReadOutcomeEnumKey = (typeof researchLinkedInReadOutcomeEnum)[keyof typeof researchLinkedInReadOutcomeEnum];

export type ResearchLinkedInRead = {
  contacts_without_linkedin: number;
  job_changes: ResearchJobChangeRead[];
  outcome: ResearchLinkedInReadOutcomeEnumKey;
  posts: ResearchPostRead[];
};
