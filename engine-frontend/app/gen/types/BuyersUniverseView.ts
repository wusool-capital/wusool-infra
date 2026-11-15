// @ts-nocheck

import type { BuyerFilterOptionsView } from './BuyerFilterOptionsView'
import type { BuyerRoleView } from './BuyerRoleView'
import type { PersonView } from './PersonView'
import type { ReservedItem } from './ReservedItem'
import type { TeamMemberView } from './TeamMemberView'

export const buyersUniverseViewUnavailableEnum = {
  mandates: 'mandates',
  outreach: 'outreach',
} as const;

export type BuyersUniverseViewUnavailableEnumKey = (typeof buyersUniverseViewUnavailableEnum)[keyof typeof buyersUniverseViewUnavailableEnum];

export type BuyersUniverseView = {
  buyers: BuyerRoleView[];
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
  options: BuyerFilterOptionsView;
  people: PersonView[];
  total: number;
  unavailable: BuyersUniverseViewUnavailableEnumKey[];
  users: TeamMemberView[];
};
