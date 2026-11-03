// @ts-nocheck

import type { CandidateRead } from './CandidateRead'

export type DecisionResponse = {
  candidate: CandidateRead;
  research_channel_id: string | null;
};
