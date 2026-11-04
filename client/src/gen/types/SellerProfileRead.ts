// @ts-nocheck

import type { MoneyRead } from './MoneyRead'

export type SellerProfileRead = {
  description: string | null;
  employee_range: string | null;
  est_ebitda: MoneyRead | null;
  est_revenue: MoneyRead | null;
  founded_year: number | null;
  hq_country: string | null;
  location_count: number | null;
  sector_focus: string[];
  website: string | null;
};
