import os
import json
import pathlib
import sys
import asyncio
import uuid
from typing import Optional
from fastmcp import FastMCP, Context
from fastmcp.exceptions import ToolError
import httpx

WEB_MCP_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_OUTPUTS = os.path.abspath(os.path.join(WEB_MCP_DIR, "outputs"))
TESTS_OUTPUTS = os.path.abspath(os.path.join(os.path.dirname(WEB_MCP_DIR), "tests", "outputs"))
os.makedirs(WEB_OUTPUTS, exist_ok=True)

mcp = FastMCP("Web MCP")
RUNTIME_URL = "http://127.0.0.1:8059"


def get_session_id(ctx: Optional[Context] = None) -> str:
    if ctx is not None:
        try:
            sid = ctx.session_id
            if sid:
                return str(sid)
        except Exception:
            pass
        try:
            cid = ctx.client_id
            if cid:
                return str(cid)
        except Exception:
            pass
    return f"sess_{uuid.uuid4().hex[:12]}"


async def _open_first(client: httpx.AsyncClient, session_id: str, url: str) -> None:
    """Open `url` in this call's browser session. Each paid marketplace call is its own MCP session, so tools that act
    on a page accept the page's address and open it themselves instead of relying on an earlier call."""
    for attempt in range(2):
        try:
            resp = await client.post(f"{RUNTIME_URL}/open_page", json={"url": url, "session": session_id}, timeout=30.0)
            if resp.status_code == 200:
                return
            if resp.status_code == 500 and attempt == 0:
                await asyncio.sleep(0.5)
                continue
            try:
                detail = resp.json().get("detail", resp.text)
            except Exception:
                detail = resp.text
            raise ToolError(str(detail))
        except ToolError:
            raise
        except Exception as e:
            if attempt == 0:
                await asyncio.sleep(0.5)
                continue
            raise ToolError(f"Connection Error: {e}")


@mcp.tool()
async def web_open_page(url: str, ctx: Context = None) -> str:
    """Open a web page in the central browser."""
    session_id = get_session_id(ctx)
    async with httpx.AsyncClient() as client:
        for attempt in range(2):
            try:
                resp = await client.post(
                    f"{RUNTIME_URL}/open_page",
                    json={"url": url, "session": session_id},
                    timeout=30.0
                )
                if resp.status_code == 200:
                    return f"Opened {resp.json().get('url')}"
                if resp.status_code == 500 and attempt == 0:
                    await asyncio.sleep(0.5)
                    continue
                try:
                    detail = resp.json().get("detail", resp.text)
                except Exception:
                    detail = resp.text
                raise ToolError(str(detail))
            except ToolError:
                raise
            except Exception as e:
                if attempt == 0:
                    await asyncio.sleep(0.5)
                    continue
                raise ToolError(f"Connection Error: {e}")


@mcp.tool()
async def web_screen_shoot(
    filename: str = "screenshot.png",
    full_page: bool = False,
    scroll_to_selector: str = "",
    url: str = "",
    ctx: Context = None
) -> str:
    """Take a screenshot of a page. Pass url to open that page first in this call (otherwise the page opened earlier in
    the same session is used). If full_page is false, only the viewport is captured. Optional scroll_to_selector will
    scroll to an element before capturing."""
    session_id = get_session_id(ctx)
    if filename == "screenshot.png":
        filename = f"screenshot_{uuid.uuid4().hex[:12]}.png"

    if not os.path.isabs(filename):
        abs_path = os.path.abspath(os.path.join(WEB_OUTPUTS, filename))
    else:
        abs_path = os.path.abspath(filename)

    try:
        in_web = os.path.commonpath([abs_path, WEB_OUTPUTS]) == WEB_OUTPUTS
    except ValueError:
        in_web = False
    try:
        in_tests = os.path.commonpath([abs_path, TESTS_OUTPUTS]) == TESTS_OUTPUTS
    except ValueError:
        in_tests = False

    if not (in_web or in_tests):
        raise ToolError("path not allowed: filename must be inside web_mcp/outputs or tests/outputs")

    params = {
        "full_page": "true" if full_page else "false",
        "session": session_id
    }
    if scroll_to_selector:
        params["scroll_to_selector"] = scroll_to_selector

    async with httpx.AsyncClient() as client:
        if url:
            await _open_first(client, session_id, url)
        try:
            resp = await client.get(f"{RUNTIME_URL}/screenshot", params=params, timeout=30.0)
        except Exception as e:
            raise ToolError(f"Connection Error: {e}")

        if resp.status_code == 200:
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            with open(abs_path, "wb") as f:
                f.write(resp.content)
            return f"Screenshot saved to {abs_path}"

        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        raise ToolError(str(detail))


@mcp.tool()
async def web_page_info(url: str = "", ctx: Context = None) -> str:
    """Get information about a page. Pass url to open that page first in this call."""
    session_id = get_session_id(ctx)
    async with httpx.AsyncClient() as client:
        if url:
            await _open_first(client, session_id, url)
        try:
            resp = await client.get(
                f"{RUNTIME_URL}/page_info",
                params={"session": session_id},
                timeout=30.0
            )
        except Exception as e:
            raise ToolError(f"Connection Error: {e}")

        if resp.status_code == 200:
            return json.dumps(resp.json(), indent=2)

        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        raise ToolError(str(detail))


@mcp.tool()
async def web_click_button(selector: str, url: str = "", ctx: Context = None) -> str:
    """Click a button or element using a CSS selector. Pass url to open that page first in this call."""
    session_id = get_session_id(ctx)
    async with httpx.AsyncClient() as client:
        if url:
            await _open_first(client, session_id, url)
        try:
            resp = await client.post(
                f"{RUNTIME_URL}/click",
                json={"selector": selector, "session": session_id},
                timeout=30.0
            )
        except Exception as e:
            raise ToolError(f"Connection Error: {e}")

        if resp.status_code == 200:
            return f"Successfully clicked {selector}"

        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        raise ToolError(str(detail))


@mcp.tool()
async def send_api_request(
    url: str,
    method: str = "GET",
    headers: str = "{}",
    data: str = "{}",
    ctx: Context = None
) -> str:
    """Send an HTTP API request."""
    try:
        headers_dict = json.loads(headers) if headers else {}
        data_dict = json.loads(data) if data else {}
    except Exception as e:
        raise ToolError(f"Error parsing JSON headers or data: {e}")

    async with httpx.AsyncClient() as client:
        for attempt in range(2):
            try:
                resp = await client.post(
                    f"{RUNTIME_URL}/api_request",
                    json={"url": url, "method": method, "headers": headers_dict, "data": data_dict},
                    timeout=30.0
                )
                if resp.status_code == 200:
                    return json.dumps(resp.json(), indent=2)
                if resp.status_code == 500 and attempt == 0:
                    await asyncio.sleep(0.5)
                    continue
                try:
                    detail = resp.json().get("detail", resp.text)
                except Exception:
                    detail = resp.text
                raise ToolError(str(detail))
            except ToolError:
                raise
            except Exception as e:
                if attempt == 0:
                    await asyncio.sleep(0.5)
                    continue
                raise ToolError(f"Connection Error: {e}")


@mcp.tool()
async def ddg_search(query: str, max_results: int = 5, ctx: Context = None) -> str:
    """Search DuckDuckGo and return web search results."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                f"{RUNTIME_URL}/ddg_search",
                params={"query": query, "max_results": max_results},
                timeout=30.0
            )
        except Exception as e:
            raise ToolError(f"Connection Error: {e}")

        if resp.status_code == 200:
            return json.dumps(resp.json(), indent=2)

        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        raise ToolError(str(detail))
