import sys
from pathlib import Path
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.paths import safe_path, PathNotAllowed

mcp = FastMCP("PDF MCP")
RUNTIME_URL = "http://127.0.0.1:8105"


async def call_runtime(tool_name: str, args: dict):
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{RUNTIME_URL}/call", json={"name": tool_name, "arguments": args}, timeout=60.0)
        except Exception as e:
            raise ToolError(f"Connection Error: {e}")
        if resp.status_code != 200:
            try:
                detail = resp.json().get("detail", resp.text)
            except Exception:
                detail = resp.text
            raise ToolError(f"Error: {detail}")
        data = resp.json()
        if isinstance(data, dict) and data.get("isError"):
            content = data.get("content", [])
            msg = "\n".join(c.get("text", "") for c in content if isinstance(c, dict)) or str(data)
            raise ToolError(msg)
        return data


@mcp.tool()
async def pdf_read_all(path: str) -> str:
    """Extract full text from a PDF document."""
    try:
        safe_path(path, must_exist=True)
    except (PathNotAllowed, FileNotFoundError) as e:
        raise ToolError(str(e))
    res = await call_runtime("pdf_read_all", {"path": path})
    return str(res)


@mcp.tool()
async def pdf_search(path: str, query: str) -> str:
    """Search text within a PDF document."""
    try:
        safe_path(path, must_exist=True)
    except (PathNotAllowed, FileNotFoundError) as e:
        raise ToolError(str(e))
    res = await call_runtime("pdf_search", {"path": path, "query": query})
    return str(res)
