from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
import httpx

mcp = FastMCP("YouTube MCP")


@mcp.tool()
async def download_yt_video(url: str, format: str = "video") -> str:
    """Download a YouTube video or audio."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post("http://127.0.0.1:8075/download", json={"url": url, "format": format}, timeout=600.0)
        except Exception as e:
            raise ToolError(f"Connection Error: {e}")
        if response.status_code != 200:
            try:
                detail = response.json().get("detail", response.text)
            except Exception:
                detail = response.text
            if "YouTube refused the download" in detail:
                raise ToolError(f"YouTube refused the download: {detail}")
            raise ToolError(f"Error: {detail}")
        return str(response.json())


@mcp.tool()
async def get_yt_transcript(video_id: str) -> str:
    """Get the transcript of a YouTube video."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post("http://127.0.0.1:8075/transcript", json={"video_id": video_id}, timeout=60.0)
        except Exception as e:
            raise ToolError(f"Connection Error: {e}")
        if response.status_code != 200:
            try:
                detail = response.json().get("detail", response.text)
            except Exception:
                detail = response.text
            if "YouTube refused the download" in detail:
                raise ToolError(f"YouTube refused the download: {detail}")
            raise ToolError(f"Error: {detail}")
        return str(response.json())
