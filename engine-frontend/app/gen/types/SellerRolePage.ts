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
  /**
   * @description `sector_choices` and `hq_countries` list everything Attio allows, for the add form.
   * @type object
   */
  options: SellerFilterOptionsView;
  rows: SellerRoleView[];
  total: number;
};
