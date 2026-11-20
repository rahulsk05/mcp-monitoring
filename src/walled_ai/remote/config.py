
import json
from pathlib import Path
from urllib.parse import urlparse

from walled_ai.logging_config import (
    get_logger,
    log_error,
    log_exception,
    log_info,
)

from walled_ai.remote.constants import (
    DEFAULT_CONFIG_PATH,
    DEFAULT_HOST,
    DEFAULT_PORT,
    SUPPORTED_TRANSPORT,
)
from walled_ai.remote.models import (
    RemoteGatewayConfig,
    UpstreamServerConfig,
)


logger = get_logger(__name__)


def load_config(
    config_path: Path = DEFAULT_CONFIG_PATH,
) -> RemoteGatewayConfig:
    """Load and validate remote gateway configuration."""

    log_info(logger, "Loading Remote Gateway configuration.")

    if not config_path.is_file():
        log_error(logger, "Remote Gateway configuration file not found.")
        raise FileNotFoundError(
            f"Remote gateway configuration not found: {config_path}"
        )

    try:
        with config_path.open("r", encoding="utf-8") as file:
            raw_config = json.load(file)

    except json.JSONDecodeError as exc:
        log_exception(logger, "Failed to parse Remote Gateway configuration.")
        raise ValueError(
            f"Invalid JSON configuration file: {config_path}"
        ) from exc

    except OSError:
        log_exception(logger, "Failed to read Remote Gateway configuration.")
        raise

    if not isinstance(raw_config, dict):
        log_error(logger, "Configuration root must be a JSON object.")
        raise ValueError("Configuration root must be a JSON object.")

    host = raw_config.get("host", DEFAULT_HOST)
    port = raw_config.get("port", DEFAULT_PORT)
    raw_servers = raw_config.get("servers")

    if not isinstance(host, str) or not host.strip():
        log_error(logger, "Invalid Remote Gateway host configuration.")
        raise ValueError("Gateway host must be a non-empty string.")

    if (
        not isinstance(port, int)
        or isinstance(port, bool)
        or not 1 <= port <= 65535
    ):
        log_error(logger, "Invalid Remote Gateway port configuration.")
        raise ValueError("Gateway port must be between 1 and 65535.")

    if not isinstance(raw_servers, dict) or not raw_servers:
        log_error(logger, "No upstream MCP servers configured.")
        raise ValueError(
            "At least one upstream MCP server must be configured."
        )

    servers: dict[str, UpstreamServerConfig] = {}

    for name, server_data in raw_servers.items():
        if not isinstance(name, str) or not name.strip():
            log_error(logger, "Invalid MCP server name in configuration.")
            raise ValueError(
                "MCP server names must be non-empty strings."
            )

        if not isinstance(server_data, dict):
            log_error(
                logger,
                "Invalid configuration structure for server '%s'.",
                name,
            )
            raise ValueError(
                f"Invalid configuration for MCP server '{name}'."
            )

        transport = server_data.get("transport")
        url = server_data.get("url")

        if transport != SUPPORTED_TRANSPORT:
            log_error(
                logger,
                "Unsupported transport configured for server '%s'.",
                name,
            )
            raise ValueError(
                f"Unsupported transport for '{name}': {transport}. "
                f"Only '{SUPPORTED_TRANSPORT}' is supported."
            )

        if not isinstance(url, str) or not url.strip():
            log_error(
                logger,
                "Missing or invalid URL for server '%s'.",
                name,
            )
            raise ValueError(
                f"Missing or invalid URL for MCP server '{name}'."
            )

        parsed_url = urlparse(url.strip())

        if (
            parsed_url.scheme not in {"http", "https"}
            or not parsed_url.hostname
        ):
            log_error(
                logger,
                "Invalid upstream URL for server '%s'.",
                name,
            )
            raise ValueError(
                f"Invalid upstream URL for MCP server '{name}'."
            )

        servers[name] = UpstreamServerConfig(
            name=name,
            transport=transport,
            url=url.strip(),
        )

    config = RemoteGatewayConfig(
        host=host,
        port=port,
        servers=servers,
    )

    log_info(
        logger,
        "Remote Gateway configuration loaded successfully. "
        "Configured upstream servers: %d",
        len(servers),
    )

    return config
