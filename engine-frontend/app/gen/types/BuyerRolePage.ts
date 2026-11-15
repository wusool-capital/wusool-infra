// @ts-nocheck

import type { BuyerFilterOptionsView } from './BuyerFilterOptionsView'
import type { BuyerRoleView } from './BuyerRoleView'

/**
 * @description `matched` counts rows under the filters and search; `total` counts every live buyer.
 * @type object
 */
export type BuyerRolePage = {
  matched: number;
  nextCursor: string | (null | null);
  options: BuyerFilterOptionsView;
  rows: BuyerRoleView[];
  total: number;
};
