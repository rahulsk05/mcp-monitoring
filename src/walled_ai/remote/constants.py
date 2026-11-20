from pathlib import Path


# Gateway defaults
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8001

# Configuration
DEFAULT_CONFIG_PATH = Path("config/remote_servers.json")

# Supported MCP transport
SUPPORTED_TRANSPORT = "streamable_http"

# Gateway tool routing
TOOL_NAME_SEPARATOR = "__"

# Remote HTTP security
NGROK_HOST = "roamer-glue-partition.ngrok-free.dev"

ALLOWED_HOSTS = [
    NGROK_HOST,
    f"{NGROK_HOST}:*",
    "127.0.0.1:*",
    "localhost:*",
]

ALLOWED_ORIGINS = [
    f"https://{NGROK_HOST}",
    "http://127.0.0.1:*",
    "http://localhost:*",
]