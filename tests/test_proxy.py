import asyncio
import sys
import unittest

from walled_ai.config import ProxyConfig
from walled_ai.proxy import start_upstream, stop_upstream


class TestUpstreamProcess(unittest.IsolatedAsyncioTestCase):

    async def test_start_upstream_process(self):
        config = ProxyConfig(
            server_name="test-server",
            upstream_command=[
                sys.executable,
                "-c",
                "print('MCP test process started')",
            ],
        )

        process = await start_upstream(config)

        self.assertIsNotNone(process.pid)

        return_code = await process.wait()

        self.assertEqual(return_code, 0)

    async def test_stop_upstream_process(self):
        config = ProxyConfig(
            server_name="test-server",
            upstream_command=[
                sys.executable,
                "-c",
                "import time; time.sleep(60)",
            ],
        )

        process = await start_upstream(config)

        self.assertIsNone(process.returncode)

        await stop_upstream(process)

        self.assertIsNotNone(process.returncode)


if __name__ == "__main__":
    unittest.main()