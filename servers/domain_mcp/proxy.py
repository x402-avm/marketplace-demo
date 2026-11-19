from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
import httpx

mcp = FastMCP("Domain Recon")

API_BASE = "http://127.0.0.1:8070"

async def _fetch(url: str) -> str:
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(url, timeout=30.0)
        except Exception as e:
            raise ToolError(f"Connection Error: {e}")
        if r.status_code != 200:
            detail = None
            try:
                detail = r.json().get("detail")
            except Exception:
                detail = r.text
            raise ToolError(str(detail or r.text))
        return str(r.text)

@mcp.tool()
async def domain_whois(domain: str) -> str:
    return await _fetch(f"{API_BASE}/whois/{domain}")

@mcp.tool()
async def domain_dns(domain: str) -> str:
    return await _fetch(f"{API_BASE}/dns/{domain}")

@mcp.tool()
async def domain_ssl(domain: str) -> str:
    return await _fetch(f"{API_BASE}/ssl/{domain}")

@mcp.tool()
async def domain_ip(domain: str) -> str:
    return await _fetch(f"{API_BASE}/ip/{domain}")
