import asyncio
import subprocess as std_subprocess
from dataclasses import dataclass
import json
import shutil
import sys
import threading

from walled_ai.approval import ApprovalManager
from walled_ai.approval_ui import ApprovalUIService
from walled_ai.config import ProxyConfig
from walled_ai.logging_config import get_logger, log_error, log_exception, log_info


logger = get_logger(__name__)

def start_stdin_reader(
    loop: asyncio.AbstractEventLoop,
    message_queue: asyncio.Queue[bytes | None],
) -> None:
    """Read stdin on a daemon thread and deliver messages to asyncio."""

    def read_input() -> None:
        while True:
            message = sys.stdin.buffer.readline()

            try:
                loop.call_soon_threadsafe(
                    message_queue.put_nowait,
                    message if message else None,
                )
            except RuntimeError:
                # The asyncio loop has already shut down.
                return

            if not message:
                return

    reader_thread = threading.Thread(
        target=read_input,
        name="walled-ai-stdin-reader",
        daemon=True,
    )
    reader_thread.start()


@dataclass
class ToolCallInfo:
    request_id: str | int
    tool_name: str
    arguments: dict[str, object]


async def start_upstream(config: ProxyConfig) -> asyncio.subprocess.Process:
    """Start the configured upstream MCP server."""

    log_info(
        logger,
        "Starting upstream MCP server | server=%s",
        config.server_name,
    )

    command = list(config.upstream_command)

    if sys.platform == "win32" and command[0].lower() in {"npx", "npx.cmd"}:
        process = await asyncio.create_subprocess_exec(
            "cmd.exe",
            "/d",
            "/c",
            *command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    else:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

    log_info(
        logger,
        "Upstream MCP server started | server=%s | pid=%s",
        config.server_name,
        process.pid,
    )

    return process


async def stop_upstream(
    process: asyncio.subprocess.Process,
) -> None:
    """Terminate the upstream process and wait for it to exit."""

    if process.returncode is not None:
        return

    log_info(logger, "Stopping upstream MCP server | pid=%s", process.pid)

    if process.stdin is not None and not process.stdin.is_closing():
        process.stdin.close()

    try:
        await asyncio.wait_for(process.wait(), timeout=5)

    except asyncio.TimeoutError:
        log_error(
            logger,
            "Upstream did not exit gracefully | pid=%s | terminating",
            process.pid,
        )

        process.terminate()

        try:
            await asyncio.wait_for(process.wait(), timeout=5)

        except asyncio.TimeoutError:
            log_error(
                logger,
                "Upstream did not terminate | pid=%s | killing",
                process.pid,
            )

            process.kill()
            await process.wait()

    log_info(logger, "Upstream process stopped | pid=%s", process.pid)


async def forward_client_to_server(
    process: asyncio.subprocess.Process,
    server_name: str,
    approval_manager: ApprovalManager,
    ui_service: ApprovalUIService,
    message_queue: asyncio.Queue[bytes | None],
    shutdown_event: asyncio.Event,
) -> None:
    """Read queued client messages and forward approved calls upstream."""

    if process.stdin is None:
        raise RuntimeError("Upstream stdin is unavailable")

    while not shutdown_event.is_set():
        message_task = asyncio.create_task(message_queue.get())
        shutdown_task = asyncio.create_task(shutdown_event.wait())

        done, pending = await asyncio.wait(
            [message_task, shutdown_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in pending:
            task.cancel()

        await asyncio.gather(*pending, return_exceptions=True)

        if shutdown_task in done or shutdown_event.is_set():
            break

        message = message_task.result()

        if message is None:
            log_info(logger, "Client input closed")
            break

        tool_call = inspect_tool_call(message)

        # Non-tool MCP messages pass through unchanged.
        if tool_call is None:
            process.stdin.write(message)
            await process.stdin.drain()
            continue

        log_info(
            logger,
            "Tool call intercepted | server=%s | tool=%s | request_id=%s",
            server_name,
            tool_call.tool_name,
            tool_call.request_id,
        )

        approved = await request_tool_approval(
            approval_manager=approval_manager,
            ui_service=ui_service,
            server_name=server_name,
            tool_call=tool_call,
        )

        if shutdown_event.is_set():
            break

        if approved:
            log_info(
                logger,
                "Tool call approved | server=%s | tool=%s | request_id=%s",
                server_name,
                tool_call.tool_name,
                tool_call.request_id,
            )

            # Forward the original message bytes unchanged.
            process.stdin.write(message)
            await process.stdin.drain()

        else:
            log_info(
                logger,
                "Tool call blocked | server=%s | tool=%s | request_id=%s",
                server_name,
                tool_call.tool_name,
                tool_call.request_id,
            )

            blocked_response = {
                "jsonrpc": "2.0",
                "id": tool_call.request_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": "Tool execution was blocked by the user.",
                        }
                    ],
                    "isError": True,
                },
            }

            sys.stdout.buffer.write(
                json.dumps(blocked_response).encode("utf-8") + b"\n"
            )
            sys.stdout.buffer.flush()

    if not process.stdin.is_closing():
        process.stdin.close()


async def forward_server_to_client(
    process: asyncio.subprocess.Process,
) -> None:
    """Forward messages from upstream server to MCP client."""

    if process.stdout is None:
        raise RuntimeError("Upstream stdout is unavailable")

    while True:
        message = await process.stdout.readline()

        if not message:
            log_info(logger, "Upstream stdout closed")
            break

        sys.stdout.buffer.write(message)
        sys.stdout.buffer.flush()


async def forward_server_errors(
    process: asyncio.subprocess.Process,
) -> None:
    """Forward upstream stderr to the client's stderr."""

    if process.stderr is None:
        raise RuntimeError("Upstream stderr is unavailable")

    while True:
        message = await process.stderr.readline()

        if not message:
            break

        sys.stderr.buffer.write(message)
        sys.stderr.buffer.flush()


def inspect_tool_call(message: bytes) -> ToolCallInfo | None:
    """Inspect a JSON-RPC message and extract MCP tool-call information."""

    try:
        payload = json.loads(message)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None

    if not isinstance(payload, dict):
        return None

    if payload.get("jsonrpc") != "2.0":
        return None

    if payload.get("method") != "tools/call":
        return None

    request_id = payload.get("id")

    if isinstance(request_id, bool) or not isinstance(
        request_id, (str, int)
    ):
        return None

    params = payload.get("params")

    if not isinstance(params, dict):
        return None

    tool_name = params.get("name")

    if not isinstance(tool_name, str) or not tool_name.strip():
        return None

    arguments = params.get("arguments", {})

    if not isinstance(arguments, dict):
        return None

    return ToolCallInfo(
        request_id=request_id,
        tool_name=tool_name,
        arguments=arguments,
    )


async def request_tool_approval(
    approval_manager: ApprovalManager,
    ui_service: ApprovalUIService,
    server_name: str,
    tool_call: ToolCallInfo,
) -> bool:
    request = approval_manager.create_request(
        server_name=server_name,
        request_id=tool_call.request_id,
        tool_name=tool_call.tool_name,
        arguments=tool_call.arguments,
    )

    loop = asyncio.get_running_loop()

    def on_decision(decision: bool) -> None:
        loop.call_soon_threadsafe(
            approval_manager.resolve,
            request.approval_id,
            decision,
        )

    ui_service.submit(request, on_decision)

    log_info(
        logger,
        "Waiting for tool approval | server=%s | tool=%s | request_id=%s",
        server_name,
        tool_call.tool_name,
        tool_call.request_id,
    )

    return await approval_manager.wait_for_decision(request.approval_id)


async def run_proxy(
    config: ProxyConfig,
    approval_manager: ApprovalManager,
    ui_service: ApprovalUIService,
    shutdown_event: asyncio.Event,
) -> None:
    """Start the upstream server and relay MCP communication."""

    process: asyncio.subprocess.Process | None = None
    tasks: list[asyncio.Task[None]] = []

    try:
        process = await start_upstream(config)

        loop = asyncio.get_running_loop()
        message_queue: asyncio.Queue[bytes | None] = asyncio.Queue()

        # Start the dedicated stdin reader.
        start_stdin_reader(loop, message_queue)

        client_task = asyncio.create_task(
            forward_client_to_server(
                process=process,
                server_name=config.server_name,
                approval_manager=approval_manager,
                ui_service=ui_service,
                message_queue=message_queue,
                shutdown_event=shutdown_event,
            )
        )

        server_task = asyncio.create_task(
            forward_server_to_client(process)
        )

        stderr_task = asyncio.create_task(
            forward_server_errors(process)
        )

        shutdown_task = asyncio.create_task(
            shutdown_event.wait()
        )

        tasks = [
            client_task,
            server_task,
            stderr_task,
            shutdown_task,
        ]

        # Stop when the client relay, upstream response relay,
        # or external shutdown signal completes.
        await asyncio.wait(
            [
                client_task,
                server_task,
                shutdown_task,
            ],
            return_when=asyncio.FIRST_COMPLETED,
        )

    except Exception:
        log_exception(logger, "Proxy communication failed")
        raise

    finally:
        # Ensure pending approvals default to Block.
        approval_manager.cancel_all()

        # Signal shutdown to any remaining relay tasks.
        shutdown_event.set()

        # Cancel remaining tasks.
        for task in tasks:
            if not task.done():
                task.cancel()

        if tasks:
            await asyncio.gather(
                *tasks,
                return_exceptions=True,
            )

        # Terminate upstream process.
        if process is not None:
            await stop_upstream(process)

        log_info(logger, "Proxy shutdown complete")