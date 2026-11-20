import asyncio
import threading
from contextlib import asynccontextmanager

import uvicorn
from mcp import types
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette

from walled_ai.approval import ApprovalManager
from walled_ai.approval_ui import ApprovalUIService
from walled_ai.logging_config import (
    get_logger,
    log_exception,
    log_info,
)
from walled_ai.remote.constants import (
    ALLOWED_HOSTS,
    ALLOWED_ORIGINS,
)
from walled_ai.remote.gateway import RemoteGateway
from walled_ai.remote.models import RemoteGatewayConfig
from walled_ai.remote.upstream_manager import UpstreamManager


logger = get_logger(__name__)


async def run_gateway(
    config: RemoteGatewayConfig,
    approval_manager: ApprovalManager,
    ui_service: ApprovalUIService,
    shutdown_requested: threading.Event,
) -> None:
    """Run the multi-upstream Remote MCP Gateway."""

    upstream_manager = UpstreamManager(config)

    gateway = RemoteGateway(
        upstream_manager=upstream_manager,
        approval_manager=approval_manager,
        ui_service=ui_service,
    )

    mcp = FastMCP(
        "Walled AI Remote Gateway",
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=ALLOWED_HOSTS,
            allowed_origins=ALLOWED_ORIGINS,
        ),
    )

    @mcp._mcp_server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return gateway.get_exposed_tools()

    @mcp._mcp_server.call_tool(validate_input=False)
    async def call_tool(
        tool_name: str,
        arguments: dict[str, object],
    ) -> types.CallToolResult:
        return await gateway.call_tool(
            exposed_tool_name=tool_name,
            arguments=arguments,
        )

    mcp_app = mcp.streamable_http_app()

    @asynccontextmanager
    async def lifespan(app: Starlette):
        log_info(logger, "Starting Remote Gateway.")

        try:
            await upstream_manager.connect_all()

            # Start the MCP HTTP session manager only after upstream
            # initialization has completed.
            async with mcp.session_manager.run():
                log_info(logger, "Remote Gateway MCP HTTP server is ready.")
                yield

        finally:
            log_info(logger, "Shutting down Remote Gateway.")

            approval_manager.cancel_all()

            await upstream_manager.disconnect_all()

            log_info(logger, "Remote Gateway shutdown completed.")

    app = Starlette(
        routes=mcp_app.router.routes,
        lifespan=lifespan,
    )

    server_config = uvicorn.Config(
        app,
        host=config.host,
        port=config.port,
        log_level="info",
    )

    server = uvicorn.Server(server_config)

    async def monitor_shutdown() -> None:
        while not shutdown_requested.is_set():
            await asyncio.sleep(0.1)

        log_info(logger, "Shutdown signal received by Remote Gateway.")
        approval_manager.cancel_all()
        server.should_exit = True

    shutdown_task = asyncio.create_task(monitor_shutdown())

    try:
        log_info(
            logger,
            "Starting HTTP Gateway on %s:%d",
            config.host,
            config.port,
        )

        await server.serve()

    except Exception:
        log_exception(logger, "Remote Gateway server failed.")

        raise

    finally:
        shutdown_task.cancel()

        await asyncio.gather(
            shutdown_task,
            return_exceptions=True,
        )

        approval_manager.cancel_all()