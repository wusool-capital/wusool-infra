"""Failures the ingest loop reacts to, raised by the Google clients."""


class CursorExpired(Exception):
    """Google no longer honours the saved bookmark; re-read the recent period."""
