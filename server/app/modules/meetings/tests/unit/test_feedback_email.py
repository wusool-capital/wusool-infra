"""`build_feedback_email_subject`/`build_feedback_email_body` are pure -- no
FastAPI, no SES client -- so they're tested directly rather than through a
live endpoint.
"""

from app.modules.meetings.api.feedback import (
    _CATEGORY_LABELS,
    build_feedback_email_body,
    build_feedback_email_subject,
)
from app.modules.meetings.api.schemas import DesktopFeedbackRequest, FeedbackCategory


def _request(**overrides: object) -> DesktopFeedbackRequest:
    fields = {
        "message": "Something broke",
        "category": FeedbackCategory.BUG,
        "contact": None,
        "install_id": "install-123",
        "app_version": "0.4.8",
        "platform": "macos 15.6 (aarch64)",
    }
    fields.update(overrides)
    return DesktopFeedbackRequest.model_validate(fields)


def test_every_category_has_a_subject_label() -> None:
    for category in FeedbackCategory:
        request = _request(category=category)
        subject = build_feedback_email_subject(request)
        assert _CATEGORY_LABELS[category] in subject


def test_subject_includes_install_id() -> None:
    request = _request(install_id="install-abc")
    assert "install-abc" in build_feedback_email_subject(request)


def test_subject_strips_control_characters_from_install_id() -> None:
    request = _request(install_id="inst\r\nall-1")
    subject = build_feedback_email_subject(request)
    assert "\r" not in subject
    assert "\n" not in subject


def test_body_includes_the_message_verbatim() -> None:
    request = _request(message="Recording button was unresponsive.")
    body = build_feedback_email_body(request)
    assert "Recording button was unresponsive." in body


def test_body_includes_install_id_version_and_platform() -> None:
    request = _request(install_id="install-123", app_version="0.4.8", platform="windows x86_64")
    body = build_feedback_email_body(request)
    assert "install-123" in body
    assert "0.4.8" in body
    assert "windows x86_64" in body


def test_absent_contact_leaves_no_contact_line() -> None:
    request = _request(contact=None)
    body = build_feedback_email_body(request)
    assert "Contact:" not in body


def test_contact_appears_when_present() -> None:
    request = _request(contact="dev@example.com")
    body = build_feedback_email_body(request)
    assert "Contact: dev@example.com" in body
