"""The Wusool MCP: find, add, edit and bulk-import buyers and sellers from Claude,
under each person's Slack sign-in. Only `main.py` uses it."""

from app.modules.mcp.bootstrap import McpApp, build_mcp_app

__all__ = ["McpApp", "build_mcp_app"]
