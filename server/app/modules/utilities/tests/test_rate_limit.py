from app.modules.utilities.domain.rate_limit import FixedWindowRateLimiter


def test_refund_gives_back_a_hit() -> None:
    limiter = FixedWindowRateLimiter(limit=1, window_s=60)
    assert limiter.check("k", now=0)
    assert not limiter.check("k", now=1)

    limiter.refund("k")

    assert limiter.check("k", now=2)


def test_refund_of_an_unknown_key_is_a_no_op() -> None:
    limiter = FixedWindowRateLimiter(limit=1, window_s=60)

    limiter.refund("never-seen")

    assert limiter.check("never-seen", now=0)
    assert not limiter.check("never-seen", now=1)
