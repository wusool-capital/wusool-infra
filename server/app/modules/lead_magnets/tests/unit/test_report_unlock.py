"""`ReportUnlock`: a code opens the gate once, only before it expires, only for
the report it was sent for, and only within five guesses."""

import pytest

from app.modules.lead_magnets.application.insights_report.unlock import (
    ChallengeGone,
    CodeNotSent,
    ReportUnlock,
    TooManyCodes,
    WrongCode,
)
from app.modules.lead_magnets.domain.insights_report.unlock import (
    MAX_ATTEMPTS,
    ReaderForm,
    UnlockChallenge,
    inbox_key,
)
from app.modules.lead_magnets.persistence.unlock_challenges import InMemoryUnlockChallenges

_FORM = ReaderForm(submission_id="s", name="Dana", company="Acme", email="dana@acme.ae")
_SLUG = "buyouts"


class _Mailer:
    def __init__(self) -> None:
        self.codes: list[str] = []

    async def send(
        self, *, to: list[str], from_addr: str, subject: str, body: str, is_html: bool = False
    ) -> None:
        self.codes.append(subject.rsplit(" ", 1)[-1])


class _Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock() -> _Clock:
    return _Clock()


@pytest.fixture
def mailer() -> _Mailer:
    return _Mailer()


@pytest.fixture
def unlock(mailer: _Mailer, clock: _Clock) -> ReportUnlock:
    return ReportUnlock(
        challenges=InMemoryUnlockChallenges(),
        mailer=mailer,
        email_from="contact@wusoolcapital.com",
        ttl_s=600,
        clock=clock,
    )


async def _send(unlock: ReportUnlock, form: ReaderForm = _FORM) -> str:
    return await unlock.send_code(slug=_SLUG, report_title="Buyouts", form=form)


def _wrong(code: str) -> str:
    return "000000" if code != "000000" else "111111"


async def test_the_right_code_works_until_spent(unlock, mailer) -> None:
    challenge_id = await _send(unlock)
    (code,) = mailer.codes
    assert len(code) == 6 and code.isdigit()

    assert unlock.verify(slug=_SLUG, challenge_id=challenge_id, code=code) == _FORM
    assert unlock.verify(slug=_SLUG, challenge_id=challenge_id, code=code) == _FORM, (
        "a failed save after verify must not burn the code"
    )
    unlock.spend(challenge_id)
    with pytest.raises(ChallengeGone):
        unlock.verify(slug=_SLUG, challenge_id=challenge_id, code=code)


async def test_wrong_codes_lock_the_challenge_after_five_guesses(unlock, mailer) -> None:
    challenge_id = await _send(unlock)
    (code,) = mailer.codes
    for _ in range(MAX_ATTEMPTS):
        with pytest.raises(WrongCode):
            unlock.verify(slug=_SLUG, challenge_id=challenge_id, code=_wrong(code))

    with pytest.raises(ChallengeGone):
        unlock.verify(slug=_SLUG, challenge_id=challenge_id, code=code)


async def test_an_expired_code_is_gone(unlock, mailer, clock) -> None:
    challenge_id = await _send(unlock)
    clock.now += 601

    with pytest.raises(ChallengeGone):
        unlock.verify(slug=_SLUG, challenge_id=challenge_id, code=mailer.codes[0])


async def test_a_code_only_opens_the_report_it_was_sent_for(unlock, mailer) -> None:
    challenge_id = await _send(unlock)

    with pytest.raises(ChallengeGone):
        unlock.verify(slug="other", challenge_id=challenge_id, code=mailer.codes[0])


async def test_one_address_gets_three_codes_per_window(unlock, clock) -> None:
    for _ in range(3):
        await _send(unlock)
    tagged = ReaderForm(submission_id="s", name="D", company="", email="DANA+x@acme.ae")
    with pytest.raises(TooManyCodes):
        await _send(unlock, tagged)

    clock.now += 601
    await _send(unlock)


async def test_a_failed_send_leaves_no_challenge_and_refunds_the_quota(clock) -> None:
    class _Down:
        async def send(self, **kwargs: object) -> None:
            raise RuntimeError("ses down")

    challenges = InMemoryUnlockChallenges()
    unlock = ReportUnlock(
        challenges=challenges, mailer=_Down(), email_from="x@y.z", ttl_s=600, clock=clock
    )
    for _ in range(4):
        with pytest.raises(CodeNotSent):
            await _send(unlock)
    assert challenges._challenges == {}


@pytest.mark.parametrize(
    ("email", "key"),
    [
        ("Dana@Acme.ae", "dana@acme.ae"),
        ("dana+reports@acme.ae", "dana@acme.ae"),
        ("d.a.n.a+x@gmail.com", "dana@gmail.com"),
        ("d.ana@acme.ae", "d.ana@acme.ae"),
    ],
)
def test_inbox_key_folds_aliases_of_one_inbox(email: str, key: str) -> None:
    assert inbox_key(email) == key


def test_old_challenges_are_evicted_on_the_service_clock() -> None:
    store = InMemoryUnlockChallenges()
    old = store.add(
        UnlockChallenge(slug=_SLUG, form=_FORM, code="123456", expires_at=10.0), now=0.0
    )
    store.add(UnlockChallenge(slug=_SLUG, form=_FORM, code="123456", expires_at=50.0), now=20.0)
    assert store.get(old) is None
