// @ts-nocheck

import type { DetailView } from './DetailView'

export const sellerRoleViewOpenToSellingEnum = {
  Unknown: 'Unknown',
  Interested: 'Interested',
  'Warm intro': 'Warm intro',
} as const;

export type SellerRoleViewOpenToSellingEnumKey = (typeof sellerRoleViewOpenToSellingEnum)[keyof typeof sellerRoleViewOpenToSellingEnum];

export type SellerRoleView = {
  appetiteSignal?: string | (null | null);
  companySector?: string | (null | null);
  contactIds: string[];
  details?: DetailView[];
  estEbitdaUsd: number | (null | null);
  estRevenueUsd: number | (null | null);
  etag: string;
  geography: string | (null | null);
  hq: string | (null | null);
  id: string;
  name: string;
  notes?: string | (null | null);
  openToSelling: SellerRoleViewOpenToSellingEnumKey;
  ownSector?: string | (null | null);
  ownerId: string | (null | null);
  reEngageDate: string | (null | null);
  sector: string | (null | null);
  website: string | (null | null);
};
