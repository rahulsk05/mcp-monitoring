import argparse
import asyncio
from pathlib import Path
import signal
import threading

from walled_ai.approval import ApprovalManager
from walled_ai.approval_ui import ApprovalUIService
from walled_ai.logging_config import (
    configure_logging,
    get_logger,
    log_exception,
    log_info,
)
from walled_ai.remote.config import load_config
from walled_ai.remote.constants import DEFAULT_CONFIG_PATH
from walled_ai.remote.server import run_gateway


logger = get_logger(__name__)


def main() -> None:
    """Initialize and run the Walled AI Remote Gateway."""

    configure_logging()

    parser = argparse.ArgumentParser(
        description="Walled AI Remote MCP Gateway",
    )

    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help="Path to Remote Gateway JSON configuration.",
    )

    args = parser.parse_args()

    try:
        config = load_config(config_path=Path(args.config))
    except Exception:
        log_exception(logger, "Remote Gateway configuration initialization failed.")
        return

    approval_manager = ApprovalManager()
    ui_service = ApprovalUIService()
    shutdown_requested = threading.Event()

    def handle_sigint(signum: int, frame: object) -> None:
        log_info(logger, "Interrupt received. Initiating graceful shutdown.")
        shutdown_requested.set()
        ui_service.request_shutdown()

    signal.signal(signal.SIGINT, handle_sigint)

    def remote_thread() -> None:
        """Run the asynchronous gateway on a dedicated thread."""

        try:
            asyncio.run(
                run_gateway(
                    config=config,
                    approval_manager=approval_manager,
                    ui_service=ui_service,
                    shutdown_requested=shutdown_requested,
                )
            )

        except Exception:
            log_exception(logger, "Remote Gateway thread failed.")

        finally:
            shutdown_requested.set()
            ui_service.request_shutdown()

    log_info(logger, "Initializing Walled AI Remote Gateway.")

    # Tkinter must be initialized and run on the main thread.
    ui_service.start()

    thread = threading.Thread(
        target=remote_thread,
        name="walled-ai-remote-gateway",
        daemon=False,
    )

    thread.start()

    try:
        ui_service.run()

    except Exception:
        log_exception(logger, "Approval UI encountered an unexpected error.")

    finally:
        log_info(logger, "Main thread initiating shutdown.")
        shutdown_requested.set()
        ui_service.request_shutdown()
        thread.join()

    log_info(logger, "Walled AI Remote Gateway stopped.")


if __name__ == "__main__":
    main()