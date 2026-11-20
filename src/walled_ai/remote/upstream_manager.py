
from contextlib import AsyncExitStack

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import Tool

from walled_ai.logging_config import (
    get_logger,
    log_error,
    log_exception,
    log_info,
)
from walled_ai.remote.models import RemoteGatewayConfig


logger = get_logger(__name__)


class UpstreamManager:
    """Manage connections and sessions for configured MCP upstream servers."""

    def __init__(self, config: RemoteGatewayConfig) -> None:
        self._config = config
        self._sessions: dict[str, ClientSession] = {}
        self._tools: dict[str, list[Tool]] = {}
        self._exit_stacks: dict[str, AsyncExitStack] = {}

    async def connect_all(self) -> None:
        """Connect to all configured upstream MCP servers."""

        log_info(
            logger,
            "Connecting to %d configured upstream MCP servers.",
            len(self._config.servers),
        )

        for server_name, server_config in self._config.servers.items():
            try:
                await self._connect_server(
                    server_name,
                    server_config.url,
                )
            except Exception:
                log_exception(
                    logger,
                    "Failed to connect to upstream MCP server '%s'.",
                    server_name,
                )

        if not self._sessions:
            log_error(logger, "No upstream MCP servers connected successfully.")
            raise RuntimeError(
                "Remote Gateway could not connect to any upstream MCP server."
            )

        log_info(
            logger,
            "Upstream connection initialization completed. "
            "Connected servers: %d/%d",
            len(self._sessions),
            len(self._config.servers),
        )

    async def _connect_server(
        self,
        server_name: str,
        upstream_url: str,
    ) -> None:
        """Establish a connection and discover tools for one upstream."""

        exit_stack = AsyncExitStack()

        try:
            read_stream, write_stream, _ = await exit_stack.enter_async_context(
                streamablehttp_client(upstream_url)
            )

            session = await exit_stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )

            await session.initialize()

            tools_result = await session.list_tools()

            self._sessions[server_name] = session
            self._tools[server_name] = tools_result.tools
            self._exit_stacks[server_name] = exit_stack

            log_info(
                logger,
                "Connected to upstream '%s'. Discovered tools: %d",
                server_name,
                len(tools_result.tools),
            )

        except Exception:
            try:
                await exit_stack.aclose()
            except Exception:
                log_exception(
                    logger,
                    "Cleanup failed after connection error for upstream '%s'.",
                    server_name,
                )
            raise

    def get_session(self, server_name: str) -> ClientSession | None:
        """Retrieve the active MCP session for a server."""

        return self._sessions.get(server_name)

    def get_tools(self, server_name: str) -> list[Tool]:
        """Retrieve discovered tools for a server."""

        return list(self._tools.get(server_name, []))

    def get_all_tools(self) -> dict[str, list[Tool]]:
        """Retrieve tools grouped by upstream server."""

        return {
            server_name: list(tools)
            for server_name, tools in self._tools.items()
        }

    def get_connected_servers(self) -> list[str]:
        """Return names of successfully connected upstream servers."""

        return list(self._sessions.keys())

    async def disconnect_all(self) -> None:
        """Close all upstream MCP sessions and transports."""

        log_info(logger, "Closing upstream MCP connections.")

        for server_name, exit_stack in list(self._exit_stacks.items()):
            try:
                await exit_stack.aclose()
                log_info(
                    logger,
                    "Disconnected upstream MCP server '%s'.",
                    server_name,
                )
            except Exception:
                log_exception(
                    logger,
                    "Error while disconnecting upstream '%s'.",
                    server_name,
                )

        self._sessions.clear()
        self._tools.clear()
        self._exit_stacks.clear()

        log_info(logger, "Upstream MCP cleanup completed.")
