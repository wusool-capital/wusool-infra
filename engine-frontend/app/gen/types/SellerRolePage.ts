// @ts-nocheck

import type { SellerFilterOptionsView } from './SellerFilterOptionsView'
import type { SellerRoleView } from './SellerRoleView'

export type SellerRolePage = {
  matched: number;
  nextCursor: string | (null | null);
  options: SellerFilterOptionsView;
  rows: SellerRoleView[];
  total: number;
};
