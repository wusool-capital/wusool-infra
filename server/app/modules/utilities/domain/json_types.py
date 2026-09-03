"""Explicit types for JSON-shaped values crossing external boundaries."""

from typing import Any

JsonObject = dict[str, Any]
JsonArray = list[Any]
AttioRecord = JsonObject
AttioPayload = JsonObject
SlackBlock = JsonObject
SlackView = JsonObject
JsonSchema = JsonObject
