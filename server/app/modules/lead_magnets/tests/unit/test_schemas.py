"""`domain/shared/schemas.py` — the models that replaced `pipelines.py`'s
manual `payload.get(key)` + `isinstance` parsing.
"""

from app.modules.lead_magnets.domain.shared.schemas import (
    AttioIdentityPayload,
    BenchmarkPayload,
    BuyerNetworkPayload,
    ReadinessPayload,
    ValuationPayload,
)


def test_benchmark_payload_parses_the_real_request_shape() -> None:
    parsed = BenchmarkPayload.model_validate(
        {
            "submission_id": "s1",
            "mode": "tech",
            "peer_key": "seed",
            "company": "Acme",
            "email": "f@acme.com",
            "revenue": 1_000_000,
            "headcount": 12,
            "consent": True,
        }
    )
    assert parsed.mode == "tech"
    assert parsed.revenue == 1_000_000
    assert parsed.headcount == 12
    assert parsed.consent is True


def test_benchmark_payload_consent_defaults_false() -> None:
    """A stored payload from before `consent` existed on this model must
    not be read as consent given."""
    parsed = BenchmarkPayload.model_validate({"peer_key": "seed"})
    assert parsed.consent is False


def test_attio_identity_payload_picks_email_and_name_out_of_a_benchmark_request() -> None:
    parsed = AttioIdentityPayload.model_validate(
        {
            "submission_id": "s1",
            "company": "Acme",
            "peer_key": "seed",
            "email": "f@acme.com",
            "name": "Dana",
            "geography": "UAE",
        }
    )
    assert parsed.email == "f@acme.com"
    assert parsed.name == "Dana"


def test_attio_identity_payload_reads_readiness_country() -> None:
    """Readiness sends `country`, not `geography` — a distinct field, not a
    fallback for the same key, since a stored payload could in principle
    carry both."""
    parsed = AttioIdentityPayload.model_validate({"company": "Acme", "country": "UAE"})
    assert parsed.country == "UAE"
    assert parsed.geography is None


def test_payload_models_ignore_write_contract_bookkeeping_keys() -> None:
    """A stored payload picks up `stage`/`ai`/`attio` (and readiness's
    `score`) after the write contract progresses — none of these are part
    of the original request, and re-parsing must not choke on them."""
    parsed = BenchmarkPayload.model_validate(
        {
            "peer_key": "seed",
            "revenue": 1.0,
            "stage": "attio",
            "ai": {"entry_values": {}, "score": 50, "band": "ok"},
            "attio": {"org_attio_id": "x"},
        }
    )
    assert parsed.peer_key == "seed"


def test_readiness_payload_parses_nested_answers() -> None:
    parsed = ReadinessPayload.model_validate(
        {
            "name": "Jane",
            "company": "Acme",
            "sector": "SaaS",
            "revenue": "1-5M",
            "country": "UAE",
            "answers": {"q1": 2, "q14": "free text"},
        }
    )
    assert parsed.answers.q1 == 2
    assert parsed.answers.q14 == "free text"
    assert parsed.answers.q2 is None


def test_valuation_payload_parses_comps_and_discounts() -> None:
    parsed = ValuationPayload.model_validate(
        {
            "revenue": 2_000_000,
            "comps": [{"co": "Tight Co", "tk": "TGT", "ev": 100, "rev": 50, "ebitda": 10}],
            "discounts": {"revenue_discount_pct": 0, "ebitda_discount_pct": 20},
        }
    )
    assert len(parsed.comps) == 1
    assert parsed.comps[0].co == "Tight Co"
    # An explicit 0% must round-trip as 0.0, not None/absent.
    assert parsed.discounts is not None
    assert parsed.discounts.revenue_discount_pct == 0


def test_valuation_payload_defaults_when_discounts_absent() -> None:
    parsed = ValuationPayload.model_validate({"revenue": 1.0})
    assert parsed.discounts is None
    assert parsed.comps == []


def test_buyer_network_payload_parses_the_real_request_shape() -> None:
    parsed = BuyerNetworkPayload.model_validate(
        {
            "org_name": "Acme Capital",
            "org_type": ["Private Equity"],
            "sector_focus": ["FinTech"],
            "target_geography": ["UAE"],
            "check_size_min": 1_000_000,
            "check_size_max": 5_000_000,
            "full_name": "Robin",
            "email": "robin@acme.com",
            "linkedin_url": "https://linkedin.com/in/robin",
        }
    )
    assert parsed.org_type == ["Private Equity"]
    assert parsed.check_size_min == 1_000_000
    assert parsed.full_name == "Robin"
    assert parsed.email == "robin@acme.com"
    assert parsed.linkedin_url == "https://linkedin.com/in/robin"
