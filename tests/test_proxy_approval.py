import asyncio
import unittest

from walled_ai.approval import ApprovalManager
from walled_ai.approval_ui import ApprovalRequest
from walled_ai.proxy import ToolCallInfo, request_tool_approval


class FakeApprovalUIService:
    """Fake UI service that captures approval requests for testing."""

    def __init__(self):
        self.request = None
        self.callback = None

    def submit(self, request: ApprovalRequest, callback) -> None:
        self.request = request
        self.callback = callback

    def decide(self, decision: bool) -> None:
        if self.callback is None:
            raise RuntimeError("No approval callback registered")

        self.callback(decision)


class TestProxyApproval(unittest.IsolatedAsyncioTestCase):

    async def test_approved_tool_call_returns_true(self):
        manager = ApprovalManager()
        ui_service = FakeApprovalUIService()

        tool_call = ToolCallInfo(
            request_id=1,
            tool_name="read_file",
            arguments={"path": "employees.txt"},
        )

        approval_task = asyncio.create_task(
            request_tool_approval(
                manager,
                ui_service,
                "filesystem",
                tool_call,
            )
        )

        await asyncio.sleep(0)

        self.assertIsNotNone(ui_service.request)
        self.assertFalse(approval_task.done())

        ui_service.decide(True)

        result = await approval_task

        self.assertTrue(result)

    async def test_blocked_tool_call_returns_false(self):
        manager = ApprovalManager()
        ui_service = FakeApprovalUIService()

        tool_call = ToolCallInfo(
            request_id=2,
            tool_name="read_file",
            arguments={"path": "secret.txt"},
        )

        approval_task = asyncio.create_task(
            request_tool_approval(
                manager,
                ui_service,
                "filesystem",
                tool_call,
            )
        )

        await asyncio.sleep(0)

        self.assertIsNotNone(ui_service.request)
        self.assertFalse(approval_task.done())

        ui_service.decide(False)

        result = await approval_task

        self.assertFalse(result)

    async def test_tool_call_waits_for_decision(self):
        manager = ApprovalManager()
        ui_service = FakeApprovalUIService()

        tool_call = ToolCallInfo(
            request_id=3,
            tool_name="list_directory",
            arguments={"path": "."},
        )

        approval_task = asyncio.create_task(
            request_tool_approval(
                manager,
                ui_service,
                "filesystem",
                tool_call,
            )
        )

        await asyncio.sleep(0)

        self.assertIsNotNone(ui_service.request)
        self.assertFalse(approval_task.done())

        ui_service.decide(True)

        result = await approval_task

        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()