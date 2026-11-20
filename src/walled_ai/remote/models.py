from dataclasses import dataclass


@dataclass(frozen=True)
class UpstreamServerConfig:
    """Configuration for a single upstream MCP server."""

    name: str
    transport: str
    url: str


@dataclass(frozen=True)
class RemoteGatewayConfig:
    """Configuration for the Walled AI remote gateway."""

    host: str
    port: int
    servers: dict[str, UpstreamServerConfig]