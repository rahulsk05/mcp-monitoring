import asyncio
import threading

from walled_ai.approval import ApprovalManager
from walled_ai.approval_ui import ApprovalUIService
from walled_ai.proxy import ToolCallInfo, request_tool_approval


def main() -> None:
    ui_service = ApprovalUIService()
    approval_manager = ApprovalManager()

    async_result: list[bool] = []
    async_finished = threading.Event()

    def async_worker() -> None:
        async def run_test() -> None:
            tool_call = ToolCallInfo(
                request_id=101,
                tool_name="read_text_file",
                arguments={"path": "employees.txt"},
            )

            decision = await request_tool_approval(
                approval_manager=approval_manager,
                ui_service=ui_service,
                server_name="filesystem",
                tool_call=tool_call,
            )

            async_result.append(decision)

            print(
                "Async worker received:",
                "ALLOW" if decision else "BLOCK",
            )

        try:
            asyncio.run(run_test())
        finally:
            async_finished.set()

    ui_service.start()

    worker = threading.Thread(
        target=async_worker,
        name="async-approval-test",
    )
    worker.start()

    print("Waiting for approval popup...")
    ui_service.run()

    worker.join(timeout=5)

    if not async_finished.is_set():
        print("TEST FAILED: async worker did not finish.")
    else:
        print("TEST PASSED: asyncio received the UI decision.")
        print(f"Result: {async_result}")


if __name__ == "__main__":
    main()