from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
import httpx

mcp = FastMCP("LaTeX MCP")


@mcp.tool()
async def compile_latex_to_pdf(latex_string: str) -> str:
    """Compiles LaTeX string to PDF and returns the path to the PDF."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post("http://127.0.0.1:8087/compile", json={"latex_string": latex_string}, timeout=30.0)
        except Exception as e:
            raise ToolError(f"Connection Error: {e}")
        if response.status_code != 200:
            try:
                detail = response.json().get("detail", response.text)
            except Exception:
                detail = response.text
            raise ToolError(f"Error: {detail}")
        return response.json()["pdf_path"]
