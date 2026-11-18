"""Composition root: builds the Wusool MCP server, wiring adapters into the tools,
and the routes `main.py` adds to the FastAPI app."""

from dataclasses import dataclass
from urllib.parse import urlsplit

from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.routing import BaseRoute, Route

from app.modules.auth import slack_sign_in_configured
from app.modules.mcp.api.oauth import CALLBACK_PATH, WusoolOAuthProvider
from app.modules.mcp.api.runner import CallerSource, ToolRunner, caller_from_token
from app.modules.mcp.api.tokens import CODE_SECONDS, TokenCodec
from app.modules.mcp.api.tools import benchmark, imports, lookups, records
from app.modules.mcp.application.ports.audit import ToolCallAudit
from app.modules.mcp.config import McpSettings, get_settings
from app.modules.mcp.domain.access import CRM_SCOPE
from app.modules.mcp.persistence.adapters import ActiveMemberPermissions, InMemoryIdempotencyStore
from app.modules.mcp.persistence.audit import ActivityToolCallAudit
from app.modules.utilities import FixedWindowRateLimiter

_INSTRUCTIONS = (
    "Wusool's CRM of buyers and sellers. Look a company up before adding or editing it. "
    "Every add and edit is saved straight away under the signed-in person's name; a bulk "
    "list is only saved after the person confirms the preview. Nothing here deletes records. "
    "To filter, call list_field_options for the keys and exact values you need, then pass "
    "only those fields as list_buyers or list_sellers `filters`. To rank or compare by "
    "numbers, page through the list (while `truncated`, call again with `offset` set to the "
    "returned `next_offset`), then pass all the role_ids to get_buyer or get_seller "
    "in one call. Their default fields cover what an advisor decides on; ask for more with "
    "`fields`, and use `return_all` only when the default lacks what you need. "
    "It also holds the GCC SME Benchmark's peer dataset. Read a row before editing it: it shows "
    "who last changed it, by name, and when. Old values are not kept, so tell the person what "
    "a row held before you overwrite it. A benchmark edit changes what visitors to the public "
    "benchmark are scored against straight away. Every change and every tool call is recorded "
    "against the signed-in person (never against Claude), so refer to them by name."
)


@dataclass(frozen=True)
class McpApp:
    server: MCPServer
    routes: list[BaseRoute]


def build_server(
    *,
    public_url: str,
    token_secret: str,
    calls_per_hour: int,
    caller_source: CallerSource,
    audit: ToolCallAudit,
) -> MCPServer:
    base = public_url.rstrip("/")
    provider = WusoolOAuthProvider(
        public_url=base,
        codec=TokenCodec(token_secret.encode()),
        used_codes=InMemoryIdempotencyStore(ttl_seconds=CODE_SECONDS * 2),
    )
    server = MCPServer(
        name="wusool",
        title="Wusool",
        instructions=_INSTRUCTIONS,
        auth_server_provider=provider,
        auth=AuthSettings(
            issuer_url=base,
            resource_server_url=f"{base}/mcp",
            validate_token_resource=True,
            required_scopes=[CRM_SCOPE],
            client_registration_options=ClientRegistrationOptions(
                enabled=True, valid_scopes=[CRM_SCOPE], default_scopes=[CRM_SCOPE]
            ),
        ),
    )
    server.custom_route(CALLBACK_PATH, methods=["GET"])(provider.slack_callback)
    runner = ToolRunner(
        permissions=ActiveMemberPermissions(),
        results=InMemoryIdempotencyStore(),
        limiter=FixedWindowRateLimiter(limit=calls_per_hour),
        audit=audit,
        caller_source=caller_source,
    )
    records.register(server, runner)
    imports.register(server, runner)
    benchmark.register(server, runner)
    lookups.register(server, runner)
    return server


def build_mcp_app(settings: McpSettings | None = None) -> McpApp | None:
    """None until MCP_PUBLIC_URL, MCP_TOKEN_SECRET and Sign in with Slack are set."""
    settings = settings or get_settings()
    if not (settings.public_url and settings.token_secret and slack_sign_in_configured()):
        return None
    server = build_server(
        public_url=settings.public_url,
        token_secret=settings.token_secret.get_secret_value(),
        calls_per_hour=settings.calls_per_hour,
        caller_source=caller_from_token,
        audit=ActivityToolCallAudit(),
    )
    public = urlsplit(settings.public_url)
    app = server.streamable_http_app(
        stateless_http=True,
        json_response=True,
        transport_security=TransportSecuritySettings(
            allowed_hosts=[public.netloc, "localhost:*", "127.0.0.1:*"],
            allowed_origins=[
                f"{public.scheme}://{public.netloc}",
                "https://claude.ai",
                "https://claude.com",
                "http://localhost:*",
                "http://127.0.0.1:*",
            ],
        ),
    )
    # Each path hands the whole MCP app the request, so its auth middleware still runs.
    routes: list[BaseRoute] = [
        Route(route.path, endpoint=app) for route in app.routes if isinstance(route, Route)
    ]
    return McpApp(server=server, routes=routes)
