// @ts-nocheck

import type { SellerFilterOptionsView } from './SellerFilterOptionsView'
import type { SellerRoleView } from './SellerRoleView'

/**
 * @description Counts and options come with the first page, as for buyers.
 * @type object
 */
export type SellerRolePage = {
  matched: number;
  nextCursor: string | (null | null);
  options: SellerFilterOptionsView;
  rows: SellerRoleView[];
  total: number;
};
