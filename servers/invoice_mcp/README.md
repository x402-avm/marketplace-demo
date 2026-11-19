# Invoice MCP Subsystem

## Overview
The Invoice MCP provides a centralized PDF generation engine built on `reportlab`. It allows AI agents to automatically generate formatted PDF invoices by passing in a structured JSON payload containing customer details, line items, and pricing.

## Architecture
- **Runtime Server (Port 8070)**: The core FastAPI backend that does the heavy lifting (parsing JSON and rendering the PDF to disk).
- **MCP Server 1 (Port 8071)**: A `fastmcp` proxy exposing the `generate_invoice` tool.
- **MCP Server 2 (Port 8072)**: A `fastmcp` proxy exposing the `generate_invoice` tool.

## Tools Exposed
- `generate_invoice(payload: dict)`: Accepts a JSON dictionary containing the invoice data and returns the absolute local path to the generated `.pdf` file.

## Execution
```bash
source venv/bin/activate
python runtime_server.py &
python mcp_server_1.py &
python mcp_server_2.py &
```
