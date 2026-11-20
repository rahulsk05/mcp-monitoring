
import asyncio

from mcp import types

from walled_ai.approval import ApprovalManager
from walled_ai.approval_ui import ApprovalUIService
from walled_ai.logging_config import (
    get_logger,
    log_error,
    log_exception,
    log_info,
    log_warning,
)
from walled_ai.remote.constants import TOOL_NAME_SEPARATOR
from walled_ai.remote.upstream_manager import UpstreamManager


logger = get_logger(__name__)


class RemoteGateway:
    """Route MCP tool calls to upstream servers with user approval."""

    def __init__(
        self,
        upstream_manager: UpstreamManager,
        approval_manager: ApprovalManager,
        ui_service: ApprovalUIService,
    ) -> None:
        self.upstream_manager = upstream_manager
        self.approval_manager = approval_manager
        self.ui_service = ui_service

        # Exposed tool name -> (upstream server, original tool name)
        self._tool_routes: dict[str, tuple[str, str]] = {}

    def get_exposed_tools(self) -> list[types.Tool]:
        """Build the exposed tool list with server-prefixed names."""

        exposed_tools: list[types.Tool] = []
        self._tool_routes.clear()

        all_tools = self.upstream_manager.get_all_tools()

        for server_name, tools in all_tools.items():
            for upstream_tool in tools:
                exposed_name = (
                    f"{server_name}"
                    f"{TOOL_NAME_SEPARATOR}"
                    f"{upstream_tool.name}"
                )

                if exposed_name in self._tool_routes:
                    log_error(
                        logger,
                        "Duplicate exposed tool name detected: '%s'.",
                        exposed_name,
                    )
                    raise ValueError(
                        f"Duplicate exposed MCP tool name: {exposed_name}"
                    )

                self._tool_routes[exposed_name] = (
                    server_name,
                    upstream_tool.name,
                )

                exposed_tools.append(
                    upstream_tool.model_copy(
                        update={"name": exposed_name}
                    )
                )

        log_info(
            logger,
            "Gateway tool discovery completed. Exposed tools: %d",
            len(exposed_tools),
        )

        return exposed_tools

    async def request_approval(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict[str, object],
    ) -> bool:
        """Request approval from the user before tool execution."""

        request = self.approval_manager.create_request(
            server_name=server_name,
            request_id=None,
            tool_name=tool_name,
            arguments=arguments,
        )

        loop = asyncio.get_running_loop()

        def on_decision(decision: bool) -> None:
            loop.call_soon_threadsafe(
                self.approval_manager.resolve,
                request.approval_id,
                decision,
            )

        try:
            self.ui_service.submit(request, on_decision)
        except Exception:
            log_exception(
                logger,
                "Failed to submit approval request | server=%s | tool=%s",
                server_name,
                tool_name,
            )

            self.approval_manager.resolve(
                request.approval_id,
                False,
            )

        return await self.approval_manager.wait_for_decision(
            request.approval_id
        )

    async def call_tool(
        self,
        exposed_tool_name: str,
        arguments: dict[str, object],
    ) -> types.CallToolResult:
        """Approve and forward a tool call to its correct upstream server."""

        route = self._tool_routes.get(exposed_tool_name)

        if route is None:
            log_warning(
                logger,
                "Received request for unknown gateway tool '%s'.",
                exposed_tool_name,
            )
            return self._error_result("Unknown MCP tool.")

        server_name, upstream_tool_name = route

        session = self.upstream_manager.get_session(server_name)

        if session is None:
            log_error(
                logger,
                "Upstream server '%s' is unavailable.",
                server_name,
            )
            return self._error_result(
                "Upstream MCP server is unavailable."
            )

        log_info(
            logger,
            "Tool request received | server=%s | tool=%s",
            server_name,
            upstream_tool_name,
        )

        try:
            approved = await self.request_approval(
                server_name=server_name,
                tool_name=upstream_tool_name,
                arguments=arguments,
            )

        except Exception:
            log_exception(
                logger,
                "Approval request failed | server=%s | tool=%s",
                server_name,
                upstream_tool_name,
            )
            return self._error_result(
                "Unable to obtain user approval."
            )

        if not approved:
            log_info(
                logger,
                "Tool execution blocked | server=%s | tool=%s",
                server_name,
                upstream_tool_name,
            )
            return self._error_result(
                "Tool execution was blocked by the user."
            )

        log_info(
            logger,
            "Tool execution approved | server=%s | tool=%s",
            server_name,
            upstream_tool_name,
        )

        try:
            result = await session.call_tool(
                upstream_tool_name,
                arguments=arguments,
            )

            log_info(
                logger,
                "Upstream tool execution completed | "
                "server=%s | tool=%s | is_error=%s",
                server_name,
                upstream_tool_name,
                result.isError,
            )

            return result

        except Exception:
            log_exception(
                logger,
                "Upstream tool execution failed | server=%s | tool=%s",
                server_name,
                upstream_tool_name,
            )
            return self._error_result(
                "Upstream tool execution failed."
            )

    @staticmethod
    def _error_result(
        message: str,
    ) -> types.CallToolResult:
        """Create a standardized MCP tool error result."""

        return types.CallToolResult(
            content=[
                types.TextContent(
                    type="text",
                    text=message,
                )
            ],
            isError=True,
        )
