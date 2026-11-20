from walled_ai.approval import ApprovalRequest
from walled_ai.approval_ui import show_approval_popup


request = ApprovalRequest(
    approval_id="test-approval-001",
    server_name="filesystem",
    request_id=3,
    tool_name="read_text_file",
    arguments={
        "path": "employees.txt",
    },
)

decision = show_approval_popup(request)

print("Decision:", "ALLOW" if decision else "BLOCK")