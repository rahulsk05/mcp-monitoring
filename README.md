# Walled AI — MCP Communication Monitoring & User Authorization

**Walled AI** is a Python-based authorization layer for Model Context Protocol (MCP) tool calls. It intercepts tool execution requests and asks the user to explicitly **Allow** or **Block** each request before it is forwarded to an upstream MCP server.

> This project is a candidate assignment prototype. It is intended for local development and demonstration, not production deployment.

## Repository and Demo

- **Repository URL:** `<REPOSITORY_URL_PLACEHOLDER>`
- **Demo video:** `<DEMO_VIDEO_URL_PLACEHOLDER>`

Replace these placeholders with the actual repository and demo links before publishing.


## Features

- Intercepts MCP tool calls before upstream execution.
- Shows the MCP server, tool name, request ID (when available), and arguments in a local approval popup.
- Requires explicit per-request approval.
- **Allow:** forwards the original tool request to the upstream MCP server.
- **Block:** prevents forwarding and returns an error result to the AI client.
- Closing the approval popup is treated as Block.
- Handles pending approvals and shutdown safely.
- Supports multiple MCP servers.
- Supports two integration paths:
  - **Claude Desktop:** local STDIO proxy that launches and relays an upstream MCP server.
  - **Claude Web:** Remote MCP Gateway using Streamable HTTP, with local approval UI and upstream routing.

## Architecture

### Claude Desktop (STDIO)

```text
Claude Desktop
    │ MCP over STDIO
    ▼
Walled AI STDIO Proxy
    │
    ├── Inspects tool calls
    ├── Displays Allow/Block approval UI
    │
    ├── Allow ──► Forward to upstream MCP server
    └── Block ──► Do not forward; return error to Claude
```

Claude Desktop launches Walled AI as its configured MCP server process. Walled AI then launches the actual upstream MCP server and relays the protocol streams.

### Claude Web (Remote Gateway)

```text
Claude Web
    │ HTTPS / Streamable HTTP
    ▼
ngrok HTTPS tunnel (for local demo)
    │
    ▼
Walled AI Remote Gateway (localhost:8001)
    │
    ├── Local Allow/Block approval popup
    ├── everything upstream (example: localhost:3001)
    ├── filesystem upstream (example: localhost:3002)
    └── other configured Streamable HTTP MCP servers
```

For Claude Web, the Gateway connects to configured upstream servers, discovers their tools, exposes the tools through its MCP endpoint, and intercepts tool calls for approval. The gateway exposes server-prefixed tool names to avoid name collisions.

## Technology Stack

- Python 3.10
- MCP Python SDK (tested with 1.30.0)
- FastMCP
- asyncio
- Tkinter
- threading
- Uvicorn and Starlette (Remote Gateway)
- Node.js, npm, and npx (for MCP servers installed/launched through npx)
- ngrok (for exposing the local Remote Gateway to Claude Web during demos)

## Prerequisites

Install the following before setup:

- Windows 10/11
- Python 3.10 (or a compatible version supported by the project)
- Git
- Node.js and npm/npx, if using Node-based upstream MCP servers
- Claude Desktop for the local STDIO integration
- Claude Web account and ability to configure a custom MCP connector for the Remote Gateway
- ngrok for the Claude Web demonstration

Verify installations in a terminal:

```bat
python --version
git --version
node --version
npm --version
npx --version
```

## Installation

### 1. Clone the repository

Replace `<REPOSITORY_URL>` with the actual repository URL:


```bat
git clone <REPOSITORY_URL>
cd mcp-monitoring
```

The folder name may differ if you clone into a custom directory. Run all subsequent commands from your actual project root.

### 2. Create and activate a virtual environment

From the project root, run:


```bat
python -m venv venv
```

**Windows Command Prompt:**

```bat
venv\Scripts\activate
```

**Windows PowerShell:**

```powershell
.\venv\Scripts\Activate.ps1
```

Confirm that the virtual environment is active and verify Python/pip:

```bat
python --version
python -m pip --version
```

### 3. Install dependencies

Upgrade pip and install project requirements:

```bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

> **Important — update the editable install path in `requirements.txt`:** The editable entry is a local path, so it must point to the directory where *you* cloned/extracted Walled AI. The example path in this repository is the developer's machine path and will not be correct for another user. Open `requirements.txt` and replace the path with your local project root. Keep the editable-install comment and `-e` entry in place. If the project is cloned to a path containing spaces, preserve quotes around the path.


## Claude Desktop Setup and Execution (STDIO)

The Desktop proxy is launched by Claude Desktop. **Do not start it manually for normal use.** Configure Claude Desktop to launch Walled AI, which then starts the upstream MCP server.

### 1. Prepare a test directory

Create or use the project's test folder and include a test file, for example:

```text
mcp-monitoring/
└── test_files/
    └── employees.txt
```

The Filesystem MCP server should be restricted to this directory. Use an absolute path to the test directory in the configuration.

### 2. Locate the Claude Desktop MCP configuration file

The configuration file location varies by installation. During development it was found under a path similar to:

```text
%LOCALAPPDATA%\Claude-Data\claude_<instance-id>\claude_desktop_config.json
```

Locate the config file used by your Claude Desktop installation and make a backup before editing it.

### 3. Add Walled AI as an MCP server

Use the Python executable from the virtual environment created in the cloned project. Replace **all example paths** with your actual clone path and test directory path. JSON paths must use escaped backslashes (`\\`).

Example configuration:

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "D:\\YOUR\\CLONE\\PATH\\mcp-monitoring\\venv\\Scripts\\python.exe",
      "args": [
        "-m",
        "walled_ai.main",
        "--server-name",
        "filesystem",
        "--",
        "npx",
        "-y",
        "@modelcontextprotocol/server-filesystem",
        "D:\\YOUR\\CLONE\\PATH\\mcp-monitoring\\test_files"
      ]
    }
  }
}
```

Configuration notes:

- `command`: the absolute path to the virtual environment's Python executable.
- `-m walled_ai.main`: launches Walled AI's STDIO proxy module.
- `--server-name filesystem`: identifies the upstream server in the approval UI and logs.
- `--`: separates Walled AI arguments from the upstream server command.
- `npx -y @modelcontextprotocol/server-filesystem`: launches the Filesystem MCP server.
- The final path is the directory the Filesystem server is allowed to access.
- Configure Claude Desktop to start **Walled AI**, not the Filesystem server directly.

### 4. Restart and test Claude Desktop

1. Save the configuration file.
2. Fully quit and restart Claude Desktop.
3. Wait for the configured MCP server to initialize.
4. Ask Claude to list the files in the configured test directory.
5. Ask Claude to read `employees.txt`.
6. Review the Walled AI approval popup.
7. Click **Allow** to forward and execute the request, or **Block** to prevent execution.

Expected behavior:

- **Allow:** the tool request is forwarded to the upstream server and its response returns to Claude.
- **Block:** the upstream operation is not executed; Claude receives an error result.
- **Close popup:** treated as Block.

### 5. Configure multiple Desktop MCP servers

Multiple entries can be added under Claude Desktop's `mcpServers` object. Each entry should use Walled AI with a unique `--server-name`, its own upstream command/arguments, and an appropriate restricted resource path. Each configured entry starts its own Walled AI proxy process.

## Claude Web Setup and Execution (Remote MCP Gateway)

The Remote Gateway uses Streamable HTTP and requires configured upstream servers to be running/reachable before the Gateway starts.

### 1. Configure upstream MCP servers

Edit:

```text
config/remote_servers.json
```

Example configuration:

```json
{
  "host": "127.0.0.1",
  "port": 8001,
  "servers": {
    "everything": {
      "transport": "streamable_http",
      "url": "http://localhost:3001/mcp"
    },
    "filesystem": {
      "transport": "streamable_http",
      "url": "http://localhost:3002/mcp"
    }
  }
}
```

The server names are unique identifiers. Tools are exposed with a server prefix (for example, `everything__echo` or `filesystem__read_text_file`) so tools with the same name on different upstreams can be routed correctly. The Gateway currently supports upstream **Streamable HTTP** MCP endpoints.

Walled AI does not install, start, update, or manage upstream servers for the Remote Gateway. Start and maintain them separately.

### 2. Start the example upstream servers

Open separate terminals from a suitable working directory.

**Everything MCP Server — port 3001:**

```bat
npx -y @modelcontextprotocol/server-everything streamableHttp
```

**Filesystem MCP Server — read-only, port 3002:**

```bat
set PORT=3002
npx -y @modelcontextprotocol/server-filesystem --transport streamable-http --read-only "<ABSOLUTE_PATH_TO_PROJECT>\test_files"
```

Replace `<ABSOLUTE_PATH_TO_PROJECT>` with the actual project directory. Keep the Filesystem server restricted to a dedicated test folder. The read-only option is recommended for the demonstration.

For a remote MCP server such as Microsoft Learn, configure its reachable endpoint in `remote_servers.json` instead of starting a local process.

### 3. Start the Remote Gateway

With the virtual environment activated and from the project root:

```bat
python -m walled_ai.remote.main
```

The Gateway loads the configuration, connects to configured upstream servers, initializes sessions, discovers tools, registers them, and starts its HTTP MCP endpoint.

Default local endpoint:

```text
http://127.0.0.1:8001
```

MCP endpoint:

```text
http://127.0.0.1:8001/mcp
```

Keep the Gateway terminal running.

### 4. Expose the local Gateway using ngrok

Open another terminal and run:


```bat
ngrok http 8001
```

Copy the HTTPS forwarding URL displayed by ngrok. The Claude Web MCP URL is that HTTPS address with `/mcp` appended, for example:

```text
https://<YOUR_NGROK_DOMAIN>/mcp
```

Keep ngrok running during use. If the tunnel stops or its URL changes, Claude Web will lose access until the tunnel is restarted and the connector URL is updated.

### 5. Configure the Claude Web custom MCP connector

In Claude Web, add a custom MCP connector using:

- **Name:** Walled AI
- **URL:** `https://<YOUR_NGROK_DOMAIN>/mcp`
- **Authentication:** None for the current demo configuration
- **Transport:** Remote MCP / Streamable HTTP

Complete the connection flow and verify that Claude Web discovers the configured upstream tools through Walled AI. If upstream servers or tools are changed, restart the Gateway and refresh/reconnect the connector so tool discovery updates.

### 6. Use the approval workflow

1. Start all configured upstream servers.
2. Start Walled AI Remote Gateway.
3. Start ngrok.
4. Confirm the Walled AI connector is connected in Claude Web.
5. Start a Claude conversation and request an action requiring an MCP tool.
6. Review the approval popup.
7. Select **Allow** or **Block**.

Allow forwards the invocation to its upstream server and returns the result to Claude. Block prevents the upstream call and returns a blocked/error result. Closing the popup is treated as denial. Pending approvals are handled during shutdown as denied.

## Configuration changes

### Claude Desktop
After changing the Claude Desktop MCP configuration, fully quit and restart Claude Desktop for the changes to take effect.

### Claude Web / Remote Gateway
After changing `config/remote_servers.json`:

1. Save the file.
2. Stop the Gateway (`Ctrl+C`).
3. Restart it with `python -m walled_ai.remote.main`.
4. Refresh/reconnect the Walled AI connector in Claude Web if the exposed tools changed.

Upstream configuration changes are not applied automatically to a running Gateway.

## Troubleshooting

| Problem | Checks / possible resolution |
|---|---|
| Walled AI does not start in Claude Desktop | Verify the venv Python path, editable installation, valid JSON, project paths, and restart Claude Desktop. |
| Upstream filesystem process fails | Verify Node.js, npm, and npx (`node --version`, `npm --version`, `npx --version`) and ensure they are available to the process launched by Claude Desktop. |
| Approval popup does not appear | Confirm Claude Desktop launched Walled AI, the request is a tool call, proxy logs show interception, and Tkinter is functioning. For Web, ensure the tool call is routed through the Walled AI connector. |
| Claude cannot read the test file | Verify the absolute test-folder path, file exists, filesystem server is restricted to the correct folder, upstream is running, and the request was allowed. |
| Claude Desktop changes not applied | Fully quit and restart Claude Desktop. |
| Remote Gateway cannot connect to upstream | Check server startup, endpoint URL, port, transport compatibility, availability, and network connectivity. |
| Claude Web cannot connect to Gateway | Verify Gateway and ngrok are running, current forwarding URL is correct, URL ends in `/mcp`, and connector is still connected. |
| Claude Web does not show newly added tools | Restart the Gateway, confirm upstream connection/tool discovery in logs, then refresh/reconnect the connector. |
| Tool fails after Allow | Review logs; possible upstream error, invalid arguments, disconnected endpoint, or network failure. |
| HTTP 405 on GET | A GET/streaming warning may be transport-specific. Verify initialization, tool discovery, and actual tool calls; a 405 warning alone may not mean the MCP connection is unusable. |

## Security notes and limitations

- The Desktop proxy intercepts tool calls that pass through its STDIO proxy. The Remote Gateway intercepts calls that pass through the Walled AI connector.
- Requests are individually approved; blocked calls are not forwarded.
- Closing an approval popup is a denial.
- The Desktop Filesystem test server should be limited to a dedicated test directory.
- The Remote Gateway binds to localhost by default, but ngrok exposes it through a public HTTPS tunnel while active.
- The current Remote Gateway has no client authentication. Host/origin validation is not user authentication.
- Do not expose the Gateway publicly without appropriate security controls.
- Avoid sensitive production data during demonstrations.
- Be cautious with tools that write files, delete data, execute commands, or modify external services.
- Native Claude integrations that bypass Walled AI are not intercepted.
- The Remote Gateway supports upstream Streamable HTTP; it does not directly launch/manage local STDIO servers.
- Walled AI does not automatically install, launch, update, or manage Remote Gateway upstream servers.
- Authenticated upstream/OAuth workflows are not guaranteed to work without additional implementation.
- Extensive stress testing and all network failure, timeout, disconnect, and cancellation cases have not been verified.
- This prototype does not provide centralized policies, identity management, audit storage, persistent logs, remote authentication, or enterprise administration.
- Stop the Gateway and ngrok tunnel when not in use.

## Testing status

### Claude Desktop
- Automated baseline: **22 tests passed** (baseline was recorded before the final live test session; the suite was not rerun afterward).
- Live initialization, tool discovery, reading a test file after Allow, blocking a tool call, sequential testing with two filesystem server configurations, and observed shutdown scenarios were verified.
- Concurrent tool calls with independent approval decisions, stress tests, extended runtime stability, and broader upstream compatibility were not verified in the Desktop implementation.

### Claude Web / Remote Gateway
Testing documented includes:
- Everything MCP tool discovery, Allow, Block, and concurrency tests.
- Filesystem MCP tool discovery and file-reading Allow flow.
- Microsoft Learn MCP tool discovery and Allow flow.
- Multiple upstream servers connected simultaneously.
- Approved calls forwarded; blocked calls denied before upstream execution.
- Independent concurrent approvals.
- Remote HTTPS MCP endpoint connection and filesystem tool invocation through the Gateway.

## Shutdown

**Claude Desktop:** closing Claude Desktop/client or terminating the proxy initiates cleanup. Pending approvals are blocked, relay tasks are cancelled, and the upstream process is stopped (with termination/kill fallback if needed). The UI is closed.

**Claude Web:** stop the Gateway and ngrok with `Ctrl+C` in their respective terminals. Stop upstream MCP servers using their own shutdown instructions. During Gateway shutdown, pending approvals are resolved as denied.

## Quick reference commands

| Purpose | Command |
|---|---|
| Clone | `git clone <REPOSITORY_URL>` |
| Create venv | `python -m venv venv` |
| Activate venv (CMD) | `venv\Scripts\activate` |
| Activate venv (PowerShell) | `.\venv\Scripts\Activate.ps1` |
| Install requirements | `python -m pip install -r requirements.txt` |
| Start Everything upstream | `npx -y @modelcontextprotocol/server-everything streamableHttp` |
| Start Filesystem upstream (read-only) | `set PORT=3002` then the filesystem command shown above |
| Start Remote Gateway | `python -m walled_ai.remote.main` |
| Start ngrok tunnel | `ngrok http 8001` |

## License

Add the project's license information here if/when a license is selected.
