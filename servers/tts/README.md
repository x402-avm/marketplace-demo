# Kokoro TTS MCP System

This project sets up a highly memory-efficient, multi-server architecture using the `kokoro-v1.0.onnx` TTS model. It features a central inference runtime server and two independent Model Context Protocol (MCP) servers, both of which connect to the same central model to prevent memory duplication and keep VRAM/RAM usage to a minimum (under ~600MB total instead of 2x that). 

## Architecture Overview
1. **Runtime Server (`runtime_server.py`)**: Runs on `127.0.0.1:8050`. It uses FastAPI to serve the Kokoro ONNX model and handles actual text-to-speech inference. Memory allocation is aggressively managed with `gc.collect()` and explicit object deletions after each request.
2. **MCP Server 1 (`mcp_server_1.py`)**: Runs on `127.0.0.1:8051`. Provides an SSE-based MCP tool `synthesize_speech`. It routes incoming text to the runtime server and saves the output to `output_server_1.wav`.
3. **MCP Server 2 (`mcp_server_2.py`)**: Runs on `127.0.0.1:8052`. Provides an identical tool, routing requests to the same central runtime server and saving to `output_server_2.wav`.

## Limits & Memory Safety
- **Strict Limits**: A strict 1000 character limit per request and a 5000 character hard limit on the runtime endpoint have been implemented to prevent excessive memory allocation during single TTS generations.
- **Context Deletion**: Explicit `del` operations on large byte buffers, text inputs, and immediate `gc.collect()` calls ensure safe context deletion right after speech generation, preventing memory leaks over time. 

## Setup & Running

**Prerequisites**:
The Python virtual environment (`venv`) includes `kokoro-onnx`, `mcp`, `fastmcp`, `fastapi`, and `uvicorn`.

**Download Model Weights**:
Before starting the runtime server for the first time, run the model download script to fetch the official ONNX model and voice library:
```bash
./download_models.sh
```

**Start the servers**:
First, start the runtime server and wait a few seconds for it to load the 325MB model:
```bash
source venv/bin/activate
python runtime_server.py
```

Then, in separate terminals, start the two MCP servers:
```bash
source venv/bin/activate
python mcp_server_1.py
```
```bash
source venv/bin/activate
python mcp_server_2.py
```

## Testing the System
A client script `test_client.py` has been provided which tests both MCP servers sequentially over SSE connections.
```bash
source venv/bin/activate
python test_client.py
```

This will trigger `synthesize_speech` on both servers and produce `output_server_1.wav` and `output_server_2.wav` in this directory.
