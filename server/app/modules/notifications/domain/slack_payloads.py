"""Bolt's own inbound payload shapes for slash commands and interactions
(button clicks, view submissions) — Slack's fixed, documented webhook
schemas, not open-ended vendor JSON like Attio's. Every handler across both
bot modules narrows Bolt's untyped `dict` parameter to these at the
boundary. Only the keys this codebase actually reads are declared; Slack's
real payloads carry more.
"""

from typing import Any, TypedDict


class SlackCommandPayload(TypedDict):
    text: str
    user_id: str
    channel_id: str
    trigger_id: str


class SlackUser(TypedDict):
    id: str


class SlackChannel(TypedDict):
    id: str


class SlackBlockAction(TypedDict, total=False):
    action_id: str
    value: str


class SlackInteractionBody(TypedDict, total=False):
    """Bolt's `body` for both `block_actions` and `view_submission`
    interactions — not every key applies to every interaction type, so all
    are optional here rather than splitting into two near-identical types.
    """

    actions: list[SlackBlockAction]
    channel: SlackChannel
    user: SlackUser


class SlackViewState(TypedDict):
    # Keyed by block_id -> action_id -> that element's state (shape varies
    # by element type - plain_text_input vs static_select vs checkboxes -
    # so `Any` here, not a further-nested TypedDict).
    values: dict[str, dict[str, Any]]


class SlackViewSubmissionPayload(TypedDict, total=False):
    id: str
    private_metadata: str
    state: SlackViewState
