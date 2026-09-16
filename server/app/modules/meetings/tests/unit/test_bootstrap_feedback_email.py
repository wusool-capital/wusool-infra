"""`bootstrap.send_feedback_email`'s orchestration: call the mailer, then
mark the row sent only on success; never raise. Uses fakes for the
mailer, sessionmaker, and repository so this runs without a real database
connection -- `FeedbackRepository.mark_email_sent`'s own correctness is
covered separately by `tests/integration/test_feedback_repository.py`,
and this exact "own session, never raise" shape has no precedent test of
its own for `run_summarize_and_publish` either; this file exists because
`send_feedback_email` has success/failure branching that one doesn't.
"""

from uuid import uuid4

import app.modules.meetings.bootstrap as bootstrap


class _FakeMailer:
    def __init__(self, *, raise_error: bool = False) -> None:
        self.raise_error = raise_error
        self.calls: list[dict] = []

    async def send(
        self, *, to: list[str], from_addr: str, subject: str, body: str, is_html: bool = False
    ) -> None:
        if self.raise_error:
            raise RuntimeError("ses is down")
        self.calls.append({"to": to, "from_addr": from_addr, "subject": subject, "body": body})


class _FakeSession:
    async def commit(self) -> None:
        pass

    async def rollback(self) -> None:
        pass


class _FakeSessionContext:
    def __init__(self, session: _FakeSession) -> None:
        self._session = session

    async def __aenter__(self) -> _FakeSession:
        return self._session

    async def __aexit__(self, *exc_info: object) -> bool:
        return False


class _FakeFeedbackRepository:
    def __init__(self) -> None:
        self.marked_sent: list = []

    async def mark_email_sent(self, *, id) -> None:  # noqa: A002 - matches the real signature
        self.marked_sent.append(id)


def _patch_session(monkeypatch, repo: _FakeFeedbackRepository) -> None:
    monkeypatch.setattr(
        bootstrap, "get_sessionmaker", lambda: lambda: _FakeSessionContext(_FakeSession())
    )
    monkeypatch.setattr(bootstrap, "build_feedback_repository", lambda session: repo)


async def test_marks_email_sent_when_the_mailer_succeeds(monkeypatch) -> None:
    repo = _FakeFeedbackRepository()
    _patch_session(monkeypatch, repo)
    mailer = _FakeMailer()
    submission_id = uuid4()

    await bootstrap.send_feedback_email(
        mailer=mailer,
        submission_id=submission_id,
        to=["team@example.com"],
        from_addr="scribe@example.com",
        subject="Scribe feedback (Bug) from install-1",
        body="body",
    )

    assert len(mailer.calls) == 1
    assert repo.marked_sent == [submission_id]


async def test_does_not_mark_email_sent_when_the_mailer_raises(monkeypatch) -> None:
    repo = _FakeFeedbackRepository()
    _patch_session(monkeypatch, repo)
    mailer = _FakeMailer(raise_error=True)

    # Must not raise -- there is no request left to hand the exception to.
    await bootstrap.send_feedback_email(
        mailer=mailer,
        submission_id=uuid4(),
        to=["team@example.com"],
        from_addr="scribe@example.com",
        subject="subject",
        body="body",
    )

    assert repo.marked_sent == []
