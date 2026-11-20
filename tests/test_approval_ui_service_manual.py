import queue
import threading

from walled_ai.approval import ApprovalRequest
from walled_ai.approval_ui import ApprovalUIService


def main() -> None:
    ui_service = ApprovalUIService()
    decision_queue: queue.Queue[bool] = queue.Queue()

    request = ApprovalRequest(
        "approval-001",
        "filesystem",
        1,
        "read_text_file",
        {"path": "employees.txt"},
    )

    def background_worker() -> None:
        print("Background thread submitting approval...")

        def callback(decision: bool) -> None:
            decision_queue.put(decision)

            # This callback executes on Tkinter's UI thread.
            ui_service.stop()

        ui_service.submit(request, callback)

        # Simulate the proxy waiting for the user's decision.
        decision = decision_queue.get()

        print(
            "Background thread received decision:",
            "ALLOW" if decision else "BLOCK",
        )

    ui_service.start()

    worker = threading.Thread(
        target=background_worker,
        name="test-background-worker",
    )

    worker.start()

    print("Tkinter main thread starting...")
    ui_service.run()

    worker.join(timeout=5)

    if worker.is_alive():
        print("Test failed: background worker did not finish.")
    else:
        print("Test passed: background worker received the decision.")


if __name__ == "__main__":
    main()