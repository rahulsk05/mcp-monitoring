import json
import queue
import tkinter as tk
from tkinter import ttk
from typing import Callable

from walled_ai.approval import ApprovalRequest


ApprovalCallback = Callable[[bool], None]
ApprovalTask = tuple[ApprovalRequest, ApprovalCallback]


class ApprovalUIService:
    """Manage approval popups on the application's main thread."""

    def __init__(self) -> None:
        self._queue: queue.Queue[ApprovalTask | None] = queue.Queue()
        self._root: tk.Tk | None = None
        self._active_popup: tk.Toplevel | None = None
        self._shutdown_requested = False
        self._active_finish: Callable[[bool], None] | None = None

    def start(self) -> None:
        """Initialize Tkinter on the main thread."""

        if self._root is not None:
            return

        self._root = tk.Tk()
        self._root.withdraw()

        self._root.after(100, self._process_queue)

    def run(self) -> None:
        """Run Tkinter's event loop on the main thread."""

        if self._root is None:
            raise RuntimeError("Approval UI has not been initialized")

        self._root.mainloop()

    def submit(
        self,
        request: ApprovalRequest,
        callback: ApprovalCallback,
    ) -> None:
        """Queue an approval request for display."""

        if self._shutdown_requested:
            callback(False)
            return

        self._queue.put((request, callback))

    def stop(self) -> None:
        """Stop the Tkinter event loop."""

        if self._root is None:
            return

        self._root.quit()
        self._root.destroy()
        self._root = None

    def request_shutdown(self) -> None:
        """Request shutdown and block all pending approvals."""
        print("DEBUG: request_shutdown() called")
        self._shutdown_requested = True

    def _process_queue(self) -> None:
        """Process queued approvals and monitor shutdown."""

        if self._root is None:
            return

        if self._shutdown_requested:
            print("DEBUG: Shutdown handling started")

            # Block the active popup, if one exists.
            if self._active_finish is not None:
                print("DEBUG: Blocking active popup")
                self._active_finish(False)

            # Block all queued approvals.
            while True:
                try:
                    task = self._queue.get_nowait()
                except queue.Empty:
                    break

                if task is not None:
                    _, callback = task
                    callback(False)

            self.stop()
            return

        # Keep monitoring while an approval popup is open.
        if self._active_popup is not None:
            self._root.after(100, self._process_queue)
            return

        try:
            task = self._queue.get_nowait()
        except queue.Empty:
            self._root.after(100, self._process_queue)
            return

        if task is None:
            self._root.after(100, self._process_queue)
            return

        request, callback = task
        self._show_popup(request, callback)

        # IMPORTANT: Schedule the next check after displaying the popup.
        self._root.after(100, self._process_queue)


    def _show_popup(
        self,
        request: ApprovalRequest,
        callback: ApprovalCallback,
    ) -> None:
        """Display one approval popup."""

        if self._root is None:
            callback(False)
            return

        popup = tk.Toplevel(self._root)
        self._active_popup = popup

        popup.title("Walled AI - Tool Approval")
        popup.resizable(True, True)
        popup.attributes("-topmost", True)

        width = 500
        height = 420

        screen_width = popup.winfo_screenwidth()
        screen_height = popup.winfo_screenheight()

        x = (screen_width - width) // 2
        y = (screen_height - height) // 2

        popup.geometry(f"{width}x{height}+{x}+{y}")

        frame = ttk.Frame(popup, padding=16)
        frame.pack(fill="both", expand=True)

        ttk.Label(
            frame,
            text="Tool Execution Approval Required",
            font=("Segoe UI", 14, "bold"),
        ).pack(anchor="w", pady=(0, 12))

        details = [
            ("MCP Server", request.server_name),
            ("Tool", request.tool_name),
            ("Request ID", str(request.request_id)),
        ]

        for label, value in details:
            row = ttk.Frame(frame)
            row.pack(fill="x", pady=3)

            ttk.Label(
                row,
                text=f"{label}:",
                width=12,
                font=("Segoe UI", 10, "bold"),
            ).pack(side="left")

            ttk.Label(
                row,
                text=value,
                font=("Segoe UI", 10),
            ).pack(side="left")

        ttk.Label(
            frame,
            text="Arguments:",
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w", pady=(8, 4))

        arguments = tk.Text(
            frame,
            height=10,
            wrap="word",
            font=("Consolas", 10),
        )

        arguments.pack(fill="both", expand=True)

        arguments.insert(
            "1.0",
            json.dumps(
                request.arguments,
                indent=2,
                ensure_ascii=False,
            ),
        )

        arguments.configure(state="disabled")

        button_frame = ttk.Frame(frame)
        button_frame.pack(fill="x", pady=(14, 0))

        resolved = False

        def finish(decision: bool) -> None:
            nonlocal resolved
            print(f"DEBUG: Popup resolved with decision={decision}")

            if resolved:
                return

            resolved = True

            root = self._root

            popup.destroy()
            self._active_popup = None
            self._active_finish = None

            # Schedule the next request before invoking the callback.

            popup.destroy()
            self._active_popup = None
            self._active_finish = None

            callback(decision)

        self._active_finish = finish

        ttk.Button(
            button_frame,
            text="Allow",
            command=lambda: finish(True),
        ).pack(side="right", padx=(8, 0))

        ttk.Button(
            button_frame,
            text="Block",
            command=lambda: finish(False),
        ).pack(side="right")

        popup.protocol(
            "WM_DELETE_WINDOW",
            lambda: finish(False),
        )

        # Explicitly show and bring the approval window to the foreground.
        popup.deiconify()
        popup.lift()
        popup.attributes("-topmost", True)
        popup.focus_force()
        popup.grab_set()