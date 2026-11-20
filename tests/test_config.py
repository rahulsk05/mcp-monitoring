import unittest

from walled_ai.config import parse_arguments

# from src.walled_ai.config import parse_arguments


class TestParseArguments(unittest.TestCase):

    def test_parses_filesystem_configuration(self):
        config = parse_arguments([
            "--server-name",
            "filesystem",
            "--",
            "npx",
            "-y",
            "@modelcontextprotocol/server-filesystem",
            r"D:\test\files",
        ])

        self.assertEqual(config.server_name, "filesystem")
        self.assertEqual(
            config.upstream_command,
            [
                "npx",
                "-y",
                "@modelcontextprotocol/server-filesystem",
                r"D:\test\files",
            ],
        )

    def test_parses_generic_server_configuration(self):
        config = parse_arguments([
            "--server-name",
            "gmail",
            "--",
            "npx",
            "-y",
            "some-gmail-mcp",
        ])

        self.assertEqual(config.server_name, "gmail")
        self.assertEqual(
            config.upstream_command,
            ["npx", "-y", "some-gmail-mcp"],
        )

    def test_missing_server_name_raises_system_exit(self):
        with self.assertRaises(SystemExit):
            parse_arguments([
                "--",
                "npx",
                "-y",
                "some-mcp-server",
            ])

    def test_missing_upstream_command_raises_system_exit(self):
        with self.assertRaises(SystemExit):
            parse_arguments([
                "--server-name",
                "filesystem",
                "--",
            ])


if __name__ == "__main__":
    unittest.main()