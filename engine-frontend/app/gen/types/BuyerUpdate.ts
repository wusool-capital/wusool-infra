// @ts-nocheck

import type { DetailInput } from './DetailInput'

/**
 * @description Only the fields sent change; a field sent as null is cleared.
 * @type object
 */
export type BuyerUpdate = {
  checkSizeMaxUsd?: number | (null | null);
  checkSizeMinUsd?: number | (null | null);
  details?: DetailInput[];
  ebitdaFloorUsd?: number | (null | null);
  geographies?: string[] | (null | null);
  notes?: string | (null | null);
  status?: string | (null | null);
};
