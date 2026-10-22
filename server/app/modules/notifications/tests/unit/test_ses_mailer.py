"""Reply-To reaches SES only when a caller sets it."""

from unittest.mock import MagicMock

from app.modules.notifications.providers.ses.mailer import SesMailer


async def _send(reply_to: str | None) -> dict[str, object]:
    client = MagicMock()
    await SesMailer(client).send(
        to=["team@wusoolcapital.com"],
        from_addr="contact@wusoolcapital.com",
        subject="Hi",
        body="<p>Hi</p>",
        is_html=True,
        reply_to=reply_to,
    )
    return client.send_email.call_args.kwargs


async def test_reply_to_is_passed_when_set() -> None:
    sent = await _send("lead@acme.com")
    assert sent["ReplyToAddresses"] == ["lead@acme.com"]
    assert sent["Source"] == "contact@wusoolcapital.com"


async def test_reply_to_is_omitted_when_unset() -> None:
    sent = await _send(None)
    assert "ReplyToAddresses" not in sent
