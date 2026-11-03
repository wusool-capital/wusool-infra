// @ts-nocheck

import type { CandidateRead } from './CandidateRead'
import type { DiscoveryRead } from './DiscoveryRead'
import type { MandateRead } from './MandateRead'

export const runDetailResponseStateEnum = {
  running: 'running',
  stale: 'stale',
  failed: 'failed',
  completed: 'completed',
} as const;

export type RunDetailResponseStateEnumKey = (typeof runDetailResponseStateEnum)[keyof typeof runDetailResponseStateEnum];

export type RunDetailResponse = {
  buyer_org_name: string;
  buyer_role_id: string;
  candidates: CandidateRead[];
  candidates_considered: number | null;
  candidates_filtered: number | null;
  completed_at: string | null;
  discovery: DiscoveryRead;
  discovery_threshold: number;
  error: string | null;
  low_match_quality: boolean;
  mandate: MandateRead | null;
  notes: string[];
  /**
   * @description
   * Format: `uuid`
   * @type string
   */
  run_id: string;
  /**
   * @description
   * Format: `date-time`
   * @type string
   */
  started_at: string;
  state: RunDetailResponseStateEnumKey;
};
