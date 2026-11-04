// @ts-nocheck

import type { ContextReadingRead } from './ContextReadingRead'
import type { DiscrepancyRead } from './DiscrepancyRead'

export type PreflightResponse = {
  buyer_role_id: string;
  conflicts: DiscrepancyRead[];
  /**
   * @description What the advisor's note was read as; amounts are absolute USD.
   * @type object
   */
  context: ContextReadingRead;
  context_checked: boolean;
  missing: DiscrepancyRead[];
};
