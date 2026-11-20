import asyncio
from dataclasses import dataclass
from uuid import uuid4

from walled_ai.logging_config import get_logger, log_debug, log_info


logger = get_logger(__name__)


@dataclass
class ApprovalRequest:
    approval_id: str
    server_name: str
    request_id: str | int | None
    tool_name: str
    arguments: dict[str, object]


class ApprovalManager:
    def __init__(self) -> None:
        self._pending: dict[str, asyncio.Future[bool]] = {}

    def create_request(
        self,
        server_name: str,
        request_id: str | int | None,
        tool_name: str,
        arguments: dict[str, object],
    ) -> ApprovalRequest:
        approval_id = str(uuid4())

        request = ApprovalRequest(
            approval_id=approval_id,
            server_name=server_name,
            request_id=request_id,
            tool_name=tool_name,
            arguments=arguments,
        )

        future: asyncio.Future[bool] = (
            asyncio.get_running_loop().create_future()
        )

        self._pending[approval_id] = future

        log_info(
            logger,
            "Approval created | server=%s | tool=%s | request_id=%s",
            server_name,
            tool_name,
            request_id,
        )

        return request

    async def wait_for_decision(
        self,
        approval_id: str,
    ) -> bool:
        future = self._pending.get(approval_id)

        if future is None:
            raise KeyError(f"Unknown approval ID: {approval_id}")

        try:
            decision = await future
            return decision
        finally:
            self._pending.pop(approval_id, None)

    def resolve(
        self,
        approval_id: str,
        decision: bool,
    ) -> bool:
        future = self._pending.get(approval_id)

        if future is None or future.done():
            log_debug(
                logger,
                "Approval already resolved or not found | id=%s",
                approval_id,
            )
            return False

        future.set_result(decision)

        log_info(
            logger,
            "Approval resolved | id=%s | decision=%s",
            approval_id,
            "ALLOW" if decision else "BLOCK",
        )

        return True

    def cancel_all(self) -> None:
        for approval_id, future in self._pending.items():
            if not future.done():
                future.set_result(False)

        log_info(logger, "All pending approvals blocked during shutdown")