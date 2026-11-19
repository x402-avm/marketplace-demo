from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
import httpx

mcp = FastMCP("Resume MCP")
RUNTIME_URL = "http://127.0.0.1:8099"


async def _post(endpoint: str, json_data: dict) -> str:
    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(f"{RUNTIME_URL}/{endpoint}", json=json_data, timeout=60.0)
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
async def resume_score(resume_text: str) -> str:
    return await _post("resume_score", {"resume_text": resume_text})


@mcp.tool()
async def ats_check(resume_text: str, job_description: str) -> str:
    return await _post("ats_check", {"resume_text": resume_text, "job_description": job_description})


@mcp.tool()
async def improve_resume(resume_text: str) -> str:
    return await _post("improve_resume", {"resume_text": resume_text})


@mcp.tool()
async def resume_to_pdf(resume_data: str) -> str:
    return await _post("resume_to_pdf", {"resume_data": resume_data})


@mcp.tool()
async def cover_letter(resume_text: str, job_description: str) -> str:
    return await _post("cover_letter", {"resume_text": resume_text, "job_description": job_description})


@mcp.tool()
async def portfolio_generator(projects_data: str) -> str:
    return await _post("portfolio_generator", {"projects_data": projects_data})
