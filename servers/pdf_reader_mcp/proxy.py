import sys
from pathlib import Path
from typing import Optional, List, Dict, Any
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.paths import safe_path, PathNotAllowed

mcp = FastMCP("PDF Reader MCP")
RUNTIME_URL = "http://127.0.0.1:8111"


def validate_sources(sources: List[Dict[str, Any]]):
    if not isinstance(sources, list):
        return
    for src in sources:
        if isinstance(src, dict) and "path" in src:
            p = src["path"]
            if p and isinstance(p, str) and not (p.startswith("http://") or p.startswith("https://")):
                safe_path(p, must_exist=True)


async def call_runtime_tool(tool_name: str, args: dict):
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{RUNTIME_URL}/call_tool/{tool_name}", json=args, timeout=30.0)
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
async def read_pdf(sources: List[Dict[str, Any]], sample_pages: Optional[int] = None, include_ocr_text_layer: Optional[bool] = None, include_full_text: bool = True) -> str:
    """Read a PDF file."""
    try:
        validate_sources(sources)
    except (PathNotAllowed, FileNotFoundError) as e:
        raise ToolError(str(e))

    args = {"sources": sources, "include_full_text": include_full_text}
    if sample_pages is not None:
        args["sample_pages"] = sample_pages
    if include_ocr_text_layer is not None:
        args["include_ocr_text_layer"] = include_ocr_text_layer
    res = await call_runtime_tool("read_pdf", args)
    return str(res)


@mcp.tool()
async def search_pdf(sources: List[Dict[str, Any]], query: str) -> str:
    """Search a PDF file."""
    try:
        validate_sources(sources)
    except (PathNotAllowed, FileNotFoundError) as e:
        raise ToolError(str(e))

    args = {"sources": sources, "query": query}
    res = await call_runtime_tool("search_pdf", args)
    return str(res)


@mcp.tool()
async def pdf_evidence(operation: str, sources: List[Dict[str, Any]]) -> str:
    """PDF evidence tool."""
    try:
        validate_sources(sources)
    except (PathNotAllowed, FileNotFoundError) as e:
        raise ToolError(str(e))

    args = {"operation": operation, "sources": sources}
    res = await call_runtime_tool("pdf_evidence", args)
    if operation == "inspect":
        try:
            read_res = await call_runtime_tool("read_pdf", {"sources": sources, "include_full_text": True})
            return f"{res}\n{read_res}"
        except Exception:
            pass
    return str(res)
