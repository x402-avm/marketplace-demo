# TTS MCP Services

The Model Context Protocol (MCP) servers (`mcp_server_1.py`, `mcp_server_2.py`) are built using the `fastmcp` Python SDK.

## Exposed Tools

### `synthesize_speech`
Synthesizes high-quality speech from text.

**Parameters:**
- `text` (string, required): The text to synthesize. Cannot exceed 1000 characters.
- `voice` (string, optional): The Voice ID. Defaults to `af_heart`.

**Returns:**
A success message string confirming the location of the saved `.wav` file on disk.

## Transports
Both servers utilize Server-Sent Events (SSE) transports.
- Server 1 Endpoint: `http://127.0.0.1:8051/sse`
- Server 2 Endpoint: `http://127.0.0.1:8052/sse`
