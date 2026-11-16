// @ts-nocheck

import type { DetailView } from './DetailView'

export type BuyerRoleView = {
  checkSizeMaxUsd: number | (null | null);
  checkSizeMinUsd: number | (null | null);
  companySector?: string | (null | null);
  contactIds: string[];
  details?: DetailView[];
  ebitdaFloorUsd: number | (null | null);
  etag: string;
  geographies: string[];
  hq: string | (null | null);
  id: string;
  name: string;
  notes: string | (null | null);
  ownerId: string | (null | null);
  sectors: string[];
  status: string | (null | null);
  type: string | (null | null);
  website: string | (null | null);
};
