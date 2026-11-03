import type { CandidateRead } from "@/gen/types/CandidateRead";
import type { RunDetailResponse } from "@/gen/types/RunDetailResponse";

export const RUN_ID = "4f0c6a8e-5d7b-4c1a-9f3e-2b8d1e6a7c90";

export function candidate(
  overrides: Partial<CandidateRead> = {},
): CandidateRead {
  return {
    id: "9b2e4c1d-3a5f-4e7b-8c6d-1f0a2b3c4d5e",
    rank: 1,
    origin: "crm",
    seller_org_name: "Gulf Dental Partners",
    seller_attio_id: "attio-seller-1",
    source_url: null,
    match_score: 78,
    data_confidence: 64,
    why_it_matches:
      "Dental clinic chain in Riyadh and Jeddah inside the buyer's ticket range.",
    why_chosen_over_alternatives:
      "Only shortlisted seller with audited EBITDA above $2M.",
    recommended_pitch: "Lead with the GCC roll-up thesis.",
    risks_and_gaps: "Revenue concentrated in two clinics.",
    status: "PENDING_REVIEW",
    decision: null,
    decided_at: null,
    deal_attio_id: null,
    ...overrides,
  };
}

export function run(
  overrides: Partial<RunDetailResponse> = {},
): RunDetailResponse {
  return {
    run_id: RUN_ID,
    buyer_role_id: "7d1e2f3a-4b5c-6d7e-8f90-a1b2c3d4e5f6",
    buyer_org_name: "Najd Healthcare Holdings",
    state: "completed",
    started_at: "2026-11-03T10:00:00Z",
    completed_at: "2026-11-03T10:00:41Z",
    error: null,
    candidates_considered: 214,
    candidates_filtered: 12,
    low_match_quality: false,
    discovery_threshold: 50,
    notes: [],
    discovery: { status: "not_needed", message: null, notes: [] },
    candidates: [candidate()],
    ...overrides,
  };
}

export function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
