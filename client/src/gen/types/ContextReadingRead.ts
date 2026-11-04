// @ts-nocheck

/**
 * @description What the advisor's note was read as; amounts are absolute USD.
 * @type object
 */
export type ContextReadingRead = {
  /**
   * @default []
   * @type array
   */
  countries: string[];
  ebitda_high: number | null;
  ebitda_low: number | null;
  ev_ceiling: number | null;
  region: string | null;
  revenue_high: number | null;
  revenue_low: number | null;
  /**
   * @default []
   * @type array
   */
  seller_status: string[];
  ticket_high: number | null;
  ticket_low: number | null;
  /**
   * @default []
   * @type array
   */
  verticals: string[];
};
