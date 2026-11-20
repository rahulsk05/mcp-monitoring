import asyncio
import os
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIRECTORY = PROJECT_ROOT / "src"


class TestProxyRelay(unittest.IsolatedAsyncioTestCase):

    async def test_message_reaches_upstream_and_returns(self):
        # Fake upstream: echoes input bytes without text-mode newline conversion.
        upstream_script = (
            "import sys\n"
            "for line in sys.stdin.buffer:\n"
            "    sys.stdout.buffer.write(line)\n"
            "    sys.stdout.buffer.flush()\n"
        )

        proxy_script = (
            "import asyncio\n"
            "from walled_ai.config import ProxyConfig\n"
            "from walled_ai.proxy import run_proxy\n"
            "from walled_ai.approval import ApprovalManager\n"
            "from walled_ai.approval_ui import ApprovalUIService\n"
            f"config = ProxyConfig('echo', "
            f"[{sys.executable!r}, '-c', {upstream_script!r}])\n"
            "approval_manager = ApprovalManager()\n"
            "ui_service = ApprovalUIService()\n"
            "shutdown_event = asyncio.Event()\n"
            "asyncio.run(run_proxy(config, approval_manager, ui_service, shutdown_event))\n"
        )

        env = os.environ.copy()
        env["PYTHONPATH"] = str(SRC_DIRECTORY)

        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            proxy_script,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=PROJECT_ROOT,
            env=env,
        )

        message = b'{"jsonrpc":"2.0","id":1,"method":"ping"}\n'

        try:
            assert process.stdin is not None
            assert process.stdout is not None

            process.stdin.write(message)
            await process.stdin.drain()

            response = await asyncio.wait_for(
                process.stdout.readline(),
                timeout=5,
            )

            self.assertEqual(response, message)

        finally:
            # Close input so the proxy/upstream receive EOF.
            if process.stdin is not None:
                process.stdin.close()

            # Ensure the subprocess doesn't remain running after test failure.
            try:
                await asyncio.wait_for(process.wait(), timeout=5)
            except asyncio.TimeoutError:
                process.terminate()
                await asyncio.wait_for(process.wait(), timeout=5)

            # Consume remaining stderr to close the pipe cleanly.
            if process.stderr is not None:
                await process.stderr.read()


if __name__ == "__main__":
    unittest.main()