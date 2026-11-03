// @ts-nocheck

export const discrepancyReadCriterionEnum = {
  vertical: 'vertical',
  geography: 'geography',
  ticket_band: 'ticket_band',
  ebitda: 'ebitda',
} as const;

export type DiscrepancyReadCriterionEnumKey = (typeof discrepancyReadCriterionEnum)[keyof typeof discrepancyReadCriterionEnum];

export type DiscrepancyRead = {
  criterion: DiscrepancyReadCriterionEnumKey;
  stated: string | null;
  stored: string;
};
