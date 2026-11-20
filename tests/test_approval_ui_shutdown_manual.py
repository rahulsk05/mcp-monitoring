import time
import unittest

from walled_ai.approval import ApprovalRequest
from walled_ai.approval_ui import ApprovalUIService


class CountingApprovalUIService(ApprovalUIService):
    """Track how many approval popups were actually displayed."""

    def __init__(self) -> None:
        super().__init__()
        self.popup_count = 0

    def _show_popup(self, request, callback) -> None:
        self.popup_count += 1
        print(f"Popup displayed for: {request.tool_name}")
        super()._show_popup(request, callback)


def create_request(request_id: int, tool_name: str) -> ApprovalRequest:
    return ApprovalRequest(
        approval_id=f"test-{request_id}",
        server_name="filesystem",
        request_id=request_id,
        tool_name=tool_name,
        arguments={"path": "test_files/employees.txt"},
    )


class TestApprovalUIShutdownManual(unittest.TestCase):

    def test_shutdown_blocks_active_popup(self) -> None:
        """Shutdown should automatically block an active popup."""

        ui_service = CountingApprovalUIService()
        decisions: list[bool] = []

        ui_service.start()

        request = create_request(1, "read_text_file")

        ui_service.submit(
            request,
            lambda decision: decisions.append(decision),
        )

        start_time = time.monotonic()

        def trigger_shutdown():
            elapsed = time.monotonic() - start_time
            print(f"TEST: Shutdown timer fired after {elapsed:.2f} seconds")
            ui_service.request_shutdown()

        ui_service._root.after(3000, trigger_shutdown)

        print("Waiting for popup — do not click Allow or Block...")
        ui_service.run()

        total_time = time.monotonic() - start_time

        print(f"UI shutdown complete after {total_time:.2f} seconds")
        print(f"Decision received: {decisions}")

        self.assertEqual(decisions, [False])
        self.assertEqual(ui_service.popup_count, 1)

        # Verify shutdown occurred near the expected 3-second mark.
        self.assertLess(total_time, 6.0)

    def test_shutdown_blocks_active_and_queued_approvals(self) -> None:
        """Shutdown should block all requests and display only the active one."""

        ui_service = CountingApprovalUIService()
        decisions: dict[str, bool] = {}

        ui_service.start()

        # Submit three approvals.
        for request_id in range(1, 4):
            request = create_request(
                request_id,
                f"test_tool_{request_id}",
            )

            ui_service.submit(
                request,
                lambda decision, name=request.tool_name:
                    decisions.__setitem__(name, decision),
            )

        # The first popup should be active.
        # Shutdown after 3 seconds.
        def trigger_shutdown():
            print("TEST: 3-second timer fired — requesting shutdown")
            ui_service.request_shutdown()

        ui_service._root.after(3000, trigger_shutdown)

        print("Waiting for first popup...")
        ui_service.run()

        print("UI shutdown complete")
        print(f"Decisions received: {decisions}")
        print(f"Popups displayed: {ui_service.popup_count}")

        # All three requests must be blocked.
        self.assertEqual(
            decisions,
            {
                "test_tool_1": False,
                "test_tool_2": False,
                "test_tool_3": False,
            },
        )

        # Only the first approval should have been displayed.
        self.assertEqual(ui_service.popup_count, 1)


if __name__ == "__main__":
    unittest.main()