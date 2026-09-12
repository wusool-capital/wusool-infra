"""A match candidate no longer gets its own "Enrich" button — that action
now lives only on the seller-add flow (`ddl_commands`). Here, a pending
candidate instead gets a plain-text hint pointing at `/enrich-seller`.
"""

from app.modules.matching_engine.api.slack.views.match_result import build_match_result_blocks
from app.modules.matching_engine.application.matching.use_cases import (
    MatchRunResult,
    ShortlistedResult,
)


def _result(seller_role_id: str | None) -> MatchRunResult:
    return MatchRunResult(
        run_id="run-1",
        status="GENERATED",
        buyer_org_name="Acme Buyer",
        results=[
            ShortlistedResult(
                match_result_id="mr-1",
                rank=1,
                seller_role_id=seller_role_id,
                seller_org_name="Acme Seller",
                match_score=80.0,
                data_confidence=50.0,
                why_it_matches="Good fit.",
                why_chosen_over_alternatives=None,
                recommended_pitch=None,
                risks_and_gaps=None,
            )
        ],
    )


def test_pending_candidate_has_no_enrich_button() -> None:
    blocks = [b.to_dict() for b in build_match_result_blocks(_result("seller-1"))]

    action_ids = {
        el["action_id"] for b in blocks if b.get("type") == "actions" for el in b["elements"]
    }

    assert "enrich_seller_from_match" not in action_ids
    assert "approve_match" in action_ids
    assert "reject_match" in action_ids
    assert "view_full_analysis" in action_ids


def test_pending_candidate_with_seller_role_shows_enrich_seller_hint() -> None:
    blocks = [b.to_dict() for b in build_match_result_blocks(_result("seller-1"))]

    context_texts = [
        el["text"] for b in blocks if b.get("type") == "context" for el in b["elements"]
    ]

    assert any("/enrich-seller Acme Seller" in text for text in context_texts)


def test_pending_candidate_without_seller_role_shows_no_hint() -> None:
    blocks = [b.to_dict() for b in build_match_result_blocks(_result(None))]

    context_texts = [
        el["text"] for b in blocks if b.get("type") == "context" for el in b["elements"]
    ]

    assert not any("/enrich-seller" in text for text in context_texts)
