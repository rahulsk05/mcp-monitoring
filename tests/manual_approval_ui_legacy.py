import asyncio
import unittest

from walled_ai.approval import ApprovalManager

# from src.walled_ai.approval import ApprovalManager

# from src.walled_ai.approval import ApprovalManager


class TestApprovalManager(unittest.IsolatedAsyncioTestCase):

    async def test_approval_can_be_allowed(self):
        manager = ApprovalManager()

        request = manager.create_request(
            server_name="filesystem",
            request_id=1,
            tool_name="read_file",
            arguments={"path": "employees.txt"},
        )

        waiter = asyncio.create_task(
            manager.wait_for_decision(request.approval_id)
        )

        manager.resolve(request.approval_id, True)

        result = await waiter

        self.assertTrue(result)

    async def test_approval_can_be_blocked(self):
        manager = ApprovalManager()

        request = manager.create_request(
            server_name="gmail",
            request_id=2,
            tool_name="search_emails",
            arguments={"query": "invoice"},
        )

        waiter = asyncio.create_task(
            manager.wait_for_decision(request.approval_id)
        )

        manager.resolve(request.approval_id, False)

        result = await waiter

        self.assertFalse(result)

    async def test_concurrent_approvals_are_independent(self):
        manager = ApprovalManager()

        request_a = manager.create_request(
            "filesystem", 1, "read_file", {"path": "a.txt"}
        )
        request_b = manager.create_request(
            "gmail", 1, "search_emails", {"query": "invoice"}
        )

        waiter_a = asyncio.create_task(
            manager.wait_for_decision(request_a.approval_id)
        )
        waiter_b = asyncio.create_task(
            manager.wait_for_decision(request_b.approval_id)
        )

        manager.resolve(request_b.approval_id, False)
        manager.resolve(request_a.approval_id, True)

        result_a, result_b = await asyncio.gather(waiter_a, waiter_b)

        self.assertTrue(result_a)
        self.assertFalse(result_b)

    async def test_cancel_all_blocks_pending_requests(self):
        manager = ApprovalManager()

        request = manager.create_request(
            "filesystem", 3, "read_file", {"path": "secret.txt"}
        )

        waiter = asyncio.create_task(
            manager.wait_for_decision(request.approval_id)
        )

        manager.cancel_all()

        result = await waiter

        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()