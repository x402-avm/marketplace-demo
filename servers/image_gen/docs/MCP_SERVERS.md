# MCP Server Configuration

All MCP servers run within the permitted port range `10000-10100`:

| Server Name | Port | Transport | Purpose |
|-------------|------|-----------|---------|
| Runtime & Web UI | `10000` | HTTP / REST | Serves Gemini Nano Banana UI and Central AI Engine |
| FastMCP Server 1 | `10002` | SSE (`/sse`) | Proxies tools: `generate_image`, `edit_image`, `optimize_prompt`, `analyze_image_quality`, `get_hardware_status` |
| FastMCP Server 2 | `10003` | SSE (`/sse`) | Secondary load-balanced MCP proxy |
| FastMCP Server 3 | `10004` | SSE (`/sse`) | Tertiary MCP proxy |

## Running FastMCP Services

```bash
# Start MCP Server 1 (Port 10002)
python mcp_server_1.py

# Start MCP Server 2 (Port 10003)
python mcp_server_2.py
```
