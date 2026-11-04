// @ts-nocheck

import type { ResearchFieldRead } from './ResearchFieldRead'
import type { ResearchLinkedInRead } from './ResearchLinkedInRead'

export const researchReadStatusEnum = {
  running: 'running',
  done: 'done',
  failed: 'failed',
} as const;

export type ResearchReadStatusEnumKey = (typeof researchReadStatusEnum)[keyof typeof researchReadStatusEnum];

/**
 * @description Full research on an approved discovered seller, for review in the page.
 * @type object
 */
export type ResearchRead = {
  error: string | null;
  fields: ResearchFieldRead[];
  linkedin: ResearchLinkedInRead | null;
  reviewed: boolean;
  /**
   * @description
   * Format: `date-time`
   * @type string
   */
  started_at: string;
  status: ResearchReadStatusEnumKey;
};
