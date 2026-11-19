from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
import httpx

mcp = FastMCP("Video Edit MCP")
RUNTIME_URL = "http://127.0.0.1:8119"


@mcp.tool()
async def trim_video(video_path: str, start_sec: float = 0.0, end_sec: float = 5.0) -> str:
    """Trim a video file to specific timestamps."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{RUNTIME_URL}/trim", json={"video_path": video_path, "start_sec": start_sec, "end_sec": end_sec}, timeout=120.0)
        except Exception as e:
            raise ToolError(f"Connection Error: {e}")
        if resp.status_code != 200:
            try:
                detail = resp.json().get("detail", resp.text)
            except Exception:
                detail = resp.text
            raise ToolError(f"Error: {detail}")
        return resp.json()["output_path"]
