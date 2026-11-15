// @ts-nocheck

import type { PersonView } from './PersonView'
import type { ReservedItem } from './ReservedItem'
import type { SellerFilterOptionsView } from './SellerFilterOptionsView'
import type { SellerRoleView } from './SellerRoleView'
import type { TeamMemberView } from './TeamMemberView'

export const sellersUniverseViewUnavailableEnum = {
  mandates: 'mandates',
  outreach: 'outreach',
} as const;

export type SellersUniverseViewUnavailableEnumKey = (typeof sellersUniverseViewUnavailableEnum)[keyof typeof sellersUniverseViewUnavailableEnum];

export type SellersUniverseView = {
  counterparties?: ReservedItem[];
  deals?: ReservedItem[];
  emails?: ReservedItem[];
  matched: number;
  nextCursor: string | (null | null);
  /**
   * @description
   * Format: `date-time`
   * @type string
   */
  now: string;
  /**
   * @description `sector_choices` and `hq_countries` list everything Attio allows, for the add form.
   * @type object
   */
  options: SellerFilterOptionsView;
  people: PersonView[];
  sellers: SellerRoleView[];
  total: number;
  unavailable: SellersUniverseViewUnavailableEnumKey[];
  users: TeamMemberView[];
};
