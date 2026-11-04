// @ts-nocheck

import type { HardRequirementRead } from './HardRequirementRead'

/**
 * @description Slack's "Buyer & Mandate" section of View Full Analysis.
 * @type object
 */
export type MandateRead = {
  hard_requirements: HardRequirementRead[];
  ideal_target: string | null;
  strategic_thesis: string | null;
};
