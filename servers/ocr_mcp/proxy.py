from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
import httpx

mcp = FastMCP("OCR MCP")
RUNTIME_URL = "http://127.0.0.1:8096"


async def _post(endpoint: str, json_data: dict) -> str:
    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(f"{RUNTIME_URL}/{endpoint}", json=json_data, timeout=120.0)
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
async def image_to_text(image_url: str) -> str:
    return await _post("image_to_text", {"image_url": image_url})


@mcp.tool()
async def pdf_to_text(pdf_url: str) -> str:
    return await _post("pdf_to_text", {"pdf_url": pdf_url})


@mcp.tool()
async def handwriting_ocr(image_url: str) -> str:
    return await _post("handwriting_ocr", {"image_url": image_url})


@mcp.tool()
async def table_extraction(image_or_pdf_url: str) -> str:
    return await _post("table_extraction", {"image_or_pdf_url": image_or_pdf_url})


@mcp.tool()
async def math_ocr(image_url: str) -> str:
    return await _post("math_ocr", {"image_url": image_url})


@mcp.tool()
async def receipt_ocr(image_url: str) -> str:
    return await _post("receipt_ocr", {"image_url": image_url})


@mcp.tool()
async def barcode_reader(image_url: str) -> str:
    return await _post("barcode_reader", {"image_url": image_url})
