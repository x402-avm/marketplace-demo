from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
import httpx

mcp = FastMCP("Image Edit MCP")
RUNTIME_URL = "http://127.0.0.1:8114"


@mcp.tool()
async def compress_image(image_path: str, quality: int = 60) -> str:
    """Compress an image file and return the output path."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{RUNTIME_URL}/compress", json={"image_path": image_path, "quality": quality}, timeout=60.0)
        except Exception as e:
            raise ToolError(f"Connection Error: {e}")
        if resp.status_code != 200:
            try:
                detail = resp.json().get("detail", resp.text)
            except Exception:
                detail = resp.text
            raise ToolError(f"Error: {detail}")
        return resp.json()["output_path"]


@mcp.tool()
async def resize_image(image_path: str, width: int, height: int) -> str:
    """Resize an image to specific dimensions."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{RUNTIME_URL}/resize", json={"image_path": image_path, "width": width, "height": height}, timeout=60.0)
        except Exception as e:
            raise ToolError(f"Connection Error: {e}")
        if resp.status_code != 200:
            try:
                detail = resp.json().get("detail", resp.text)
            except Exception:
                detail = resp.text
            raise ToolError(f"Error: {detail}")
        return resp.json()["output_path"]
