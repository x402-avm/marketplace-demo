from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
import httpx
import json

mcp = FastMCP("Paper MCP")
RUNTIME_URL = "http://127.0.0.1:8125"

@mcp.tool()
async def search_papers(query: str, max_results: int = 3) -> str:
    """Search academic research papers on arXiv."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{RUNTIME_URL}/search_papers", json={"query": query, "max_results": max_results}, timeout=30.0)
        except Exception as e:
            raise ToolError(f"Connection Error: {e}")

        if resp.status_code != 200:
            detail = None
            try:
                detail = resp.json().get("detail")
            except Exception:
                detail = resp.text
            raise ToolError(f"Error: {detail or resp.text}")

        data = resp.json()
        if isinstance(data, dict) and data.get("status") == "error":
            raise ToolError(data.get("message", "Search failed"))

        return json.dumps(data, indent=2)
