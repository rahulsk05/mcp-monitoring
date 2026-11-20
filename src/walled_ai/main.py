
import asyncio
import signal
import threading

from walled_ai.approval import ApprovalManager
from walled_ai.approval_ui import ApprovalUIService
from walled_ai.config import parse_arguments
from walled_ai.logging_config import (
    configure_logging,
    get_logger,
    log_exception,
    log_info,
)
from walled_ai.proxy import run_proxy


logger = get_logger(__name__)


def run_proxy_thread(
    config,
    approval_manager: ApprovalManager,
    ui_service: ApprovalUIService,
    shutdown_requested: threading.Event,
) -> None:
    """Run the asyncio proxy in a dedicated background thread."""

    async def proxy_runner() -> None:
        shutdown_event = asyncio.Event()

        async def monitor_shutdown() -> None:
            while not shutdown_requested.is_set():
                await asyncio.sleep(0.1)

            shutdown_event.set()

        shutdown_monitor = asyncio.create_task(monitor_shutdown())

        try:
            await run_proxy(
                config=config,
                approval_manager=approval_manager,
                ui_service=ui_service,
                shutdown_event=shutdown_event,
            )
        finally:
            shutdown_monitor.cancel()
            await asyncio.gather(shutdown_monitor, return_exceptions=True)

    try:
        asyncio.run(proxy_runner())
    except Exception:
        log_exception(logger, "Proxy thread terminated unexpectedly")
    finally:
        # If the proxy stops for any reason, shut down the UI as well.
        shutdown_requested.set()
        ui_service.request_shutdown()


def main() -> None:
    config = parse_arguments()

    log_info(logger, "Starting Walled AI")
    log_info(logger, "MCP server: %s", config.server_name)

    approval_manager = ApprovalManager()
    ui_service = ApprovalUIService()
    shutdown_requested = threading.Event()

    def handle_shutdown(signum, frame) -> None:
        log_info(logger, "Shutdown signal received")
        shutdown_requested.set()
        ui_service.request_shutdown()

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    # Initialize Tkinter on the main thread.
    ui_service.start()

    proxy_thread = threading.Thread(
        target=run_proxy_thread,
        args=(
            config,
            approval_manager,
            ui_service,
            shutdown_requested,
        ),
        name="walled-ai-proxy",
        daemon=False,
    )

    proxy_thread.start()

    try:
        # Tkinter must remain on the main thread.
        ui_service.run()
    finally:
        shutdown_requested.set()
        ui_service.request_shutdown()

        # Wait for proxy cleanup to complete.
        proxy_thread.join()

        log_info(logger, "Walled AI shutdown complete")


if __name__ == "__main__":
    configure_logging()

    try:
        main()
    except KeyboardInterrupt:
        log_info(logger, "Walled AI stopped by user")
    except Exception:
        log_exception(logger, "Walled AI terminated unexpectedly")
