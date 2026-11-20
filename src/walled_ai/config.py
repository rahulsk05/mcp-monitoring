import argparse
from dataclasses import dataclass
from typing import Sequence


@dataclass
class ProxyConfig:
    server_name: str
    upstream_command: list[str]


def parse_arguments(argv: Sequence[str] | None = None) -> ProxyConfig:
    """Parse proxy configuration and upstream server command."""

    parser = argparse.ArgumentParser(
        description="Walled AI MCP monitoring proxy"
    )

    parser.add_argument(
        "--server-name",
        required=True,
        help="Name of the MCP server being proxied",
    )

    parser.add_argument(
        "upstream_command",
        nargs=argparse.REMAINDER,
        help="Command used to start the upstream MCP server",
    )

    args = parser.parse_args(argv)

    upstream_command = args.upstream_command

    # Remove the separator if argparse included it.
    if upstream_command and upstream_command[0] == "--":
        upstream_command = upstream_command[1:]

    if not upstream_command:
        parser.error("An upstream server command is required.")

    return ProxyConfig(
        server_name=args.server_name,
        upstream_command=upstream_command,
    )