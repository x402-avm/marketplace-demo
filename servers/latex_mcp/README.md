# LaTeX to PDF MCP Subsystem

## Overview
The LaTeX MCP provides a native translation engine for AI agents to write advanced mathematical/academic LaTeX strings and have them compiled directly into PDF format.

## Architecture
- **Runtime Server (Port 8083)**: Centralized FastAPI backend that drops the LaTeX payload into a temporary `.tex` file and compiles it via the system's `pdflatex` binary.
- **MCP Server 1 (Port 8084)**: Proxy node exposing the compiler tool.
- **MCP Server 2 (Port 8085)**: Proxy node exposing the compiler tool.

## Tools Exposed
- `compile_latex_to_pdf(latex_string: str)`: Compiles the LaTeX template and returns the absolute local path to the rendered PDF file.

## Execution
```bash
source venv/bin/activate
python runtime_server.py &
python mcp_server_1.py &
python mcp_server_2.py &
```
