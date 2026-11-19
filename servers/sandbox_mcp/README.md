# Multi-Language Code Sandbox MCP Subsystem

## Overview
The Code Sandbox MCP provides an isolated execution environment for compiling and running raw code snippets directly from the AI agent context. It natively supports standard IO and execution for Python, Java, JavaScript (Node), C, and C++.

## Architecture
- **Runtime Server (Port 8079)**: Centralized FastAPI backend that intercepts code strings, writes them to secure `/tmp` files, invokes the native compilers (`gcc`, `javac`, `node`, `python3`), and pipes the `stdout`/`stderr` back.
- **MCP Server 1 (Port 8081)**: Proxy node exposing the sandbox tool.
- **MCP Server 2 (Port 8082)**: Proxy node exposing the sandbox tool.

## Tools Exposed
- `run_sandbox_code(language: str, code: str)`: Compiles and executes the provided code string, returning a JSON block with `stdout` and `stderr`.

## Execution
```bash
source venv/bin/activate
python runtime_server.py &
python mcp_server_1.py &
python mcp_server_2.py &
```
