"""§33's separate Slack-transport test: does not require a real Slack
workspace. Confirms request-signature verification actually runs (§2, §37)
— an unsigned/invalid request must be rejected before anything in the
application layer sees it.
"""

from fastapi.testclient import TestClient

from app.modules.matching_engine.bootstrap import create_app

app = create_app()


def test_unsigned_slack_request_is_rejected() -> None:
    client = TestClient(app)

    response = client.post("/slack/events", json={"type": "event_callback"})

    assert response.status_code == 401
