import os
import sys

# Strictly isolate CPU
os.environ["CUDA_VISIBLE_DEVICES"] = ""

from app.config import MCP_PORT
from app.mcp.server import mcp

if __name__ == "__main__":
    port = int(os.environ.get("MCP_PORT", MCP_PORT))
    print(f"Starting Gemini Nano Banana MCP Server on http://127.0.0.1:{port}/sse ...")
    mcp.run(transport='sse', port=port, host="127.0.0.1")
