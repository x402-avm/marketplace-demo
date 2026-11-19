from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
import httpx

mcp = FastMCP("Invoice MCP")


@mcp.tool()
async def generate_invoice(customer_name: str, items: list[dict]) -> str:
    """Generate an invoice PDF."""
    async with httpx.AsyncClient() as client:
        payload = {"customer_name": customer_name, "items": items}
        try:
            response = await client.post("http://127.0.0.1:8064/generate_invoice", json=payload, timeout=30.0)
        except Exception as e:
            raise ToolError(f"Connection Error: {e}")
        if response.status_code != 200:
            try:
                detail = response.json().get("detail", response.text)
            except Exception:
                detail = response.text
            raise ToolError(f"Error: {detail}")
        return response.json()["filepath"]
