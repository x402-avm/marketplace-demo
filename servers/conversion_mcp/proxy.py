from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
import httpx
from typing import List

mcp = FastMCP("File Conversion")
RUNTIME_URL = "http://127.0.0.1:8091"


async def _post(endpoint: str, json_data: dict) -> str:
    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(f"{RUNTIME_URL}/{endpoint}", json=json_data, timeout=180.0)
        except Exception as e:
            raise ToolError(f"Connection Error: {e}")
        if r.status_code != 200:
            try:
                detail = r.json().get("detail", r.text)
            except Exception:
                detail = r.text
            raise ToolError(f"Error: {detail}")
        return r.json()["result"]


@mcp.tool()
async def document_convert(file_url: str, from_format: str, to_format: str) -> str:
    return await _post("document_convert", {"file_url": file_url, "from_format": from_format, "to_format": to_format})


@mcp.tool()
async def data_convert(file_url: str, from_format: str, to_format: str) -> str:
    return await _post("data_convert", {"file_url": file_url, "from_format": from_format, "to_format": to_format})


@mcp.tool()
async def image_convert(file_url: str, from_format: str, to_format: str) -> str:
    return await _post("image_convert", {"file_url": file_url, "from_format": from_format, "to_format": to_format})


@mcp.tool()
async def audio_convert(file_url: str, from_format: str, to_format: str) -> str:
    return await _post("audio_convert", {"file_url": file_url, "from_format": from_format, "to_format": to_format})


@mcp.tool()
async def video_convert(file_url: str, from_format: str, to_format: str) -> str:
    return await _post("video_convert", {"file_url": file_url, "from_format": from_format, "to_format": to_format})


@mcp.tool()
async def archive_create(file_urls: List[str], format: str) -> str:
    return await _post("archive_create", {"file_urls": file_urls, "format": format})


@mcp.tool()
async def archive_extract(file_url: str, format: str) -> str:
    return await _post("archive_extract", {"file_url": file_url, "format": format})
