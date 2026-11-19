import asyncio
import collections
import io
import os
import pathlib
import sys
from typing import Any, Dict, Optional
import urllib.parse
from ddgs import DDGS
import fastapi
import httpx
from playwright.async_api import Browser, BrowserContext, Page, async_playwright
from playwright_stealth import Stealth
from pydantic import BaseModel
import uvicorn

SERVERS_DIR = pathlib.Path(__file__).resolve().parents[1]
if str(SERVERS_DIR) not in sys.path:
    sys.path.insert(0, str(SERVERS_DIR))

from common.netguard import BlockedURL, check_url

app = fastapi.FastAPI(title="Web MCP Runtime Server")

playwright_instance = None
browser: Optional[Browser] = None

MAX_SESSIONS = 8
sessions: collections.OrderedDict[str, tuple[BrowserContext, Page]] = collections.OrderedDict()
sessions_lock = asyncio.Lock()


async def get_or_create_page(session_id: Optional[str] = None) -> Page:
    global browser
    if not session_id:
        session_id = "default"

    async with sessions_lock:
        if session_id in sessions:
            sessions.move_to_end(session_id)
            context, page = sessions[session_id]
            return page

        # LRU eviction: close oldest session if limit reached
        while len(sessions) >= MAX_SESSIONS:
            oldest_id, (old_ctx, old_page) = sessions.popitem(last=False)
            try:
                await old_ctx.close()
            except Exception as e:
                print(f"Error closing evicted session {oldest_id}: {e}")

        context = await browser.new_context()
        page = await context.new_page()
        await Stealth().apply_stealth_async(page)

        # Register route handler to abort any request failing check_url
        async def route_handler(route):
            req_url = route.request.url
            if req_url.startswith(("data:", "about:", "blob:")):
                await route.continue_()
                return
            try:
                check_url(req_url)
                await route.continue_()
            except Exception:
                await route.abort()

        await page.route("**/*", route_handler)
        sessions[session_id] = (context, page)
        return page


@app.on_event("startup")
async def startup():
    global playwright_instance, browser
    playwright_instance = await async_playwright().start()
    browser = await playwright_instance.chromium.launch(headless=True)
    await get_or_create_page("default")
    print("Playwright browser initialized with per-session support.")


@app.on_event("shutdown")
async def shutdown():
    global playwright_instance, browser, sessions
    async with sessions_lock:
        for session_id, (ctx, page) in list(sessions.items()):
            try:
                await ctx.close()
            except Exception:
                pass
        sessions.clear()
    if browser:
        await browser.close()
    if playwright_instance:
        await playwright_instance.stop()


class OpenPageRequest(BaseModel):
    url: str
    session: Optional[str] = "default"


class ClickButtonRequest(BaseModel):
    selector: str
    session: Optional[str] = "default"


class ApiRequest(BaseModel):
    url: str
    method: str = "GET"
    headers: Optional[Dict[str, str]] = None
    data: Optional[Any] = None


@app.post("/open_page")
async def open_page(req: OpenPageRequest, session: Optional[str] = fastapi.Query(None)):
    session_id = session or req.session or "default"
    try:
        check_url(req.url)
    except BlockedURL as e:
        raise fastapi.HTTPException(status_code=403, detail=str(e))

    try:
        page = await get_or_create_page(session_id)
        await page.goto(req.url, wait_until="networkidle")
        return {"status": "success", "url": page.url}
    except Exception as e:
        return fastapi.Response(content=str(e), status_code=500)


@app.get("/screenshot")
async def screenshot(
    full_page: bool = False,
    scroll_to_selector: Optional[str] = None,
    session: Optional[str] = fastapi.Query("default")
):
    session_id = session or "default"
    try:
        page = await get_or_create_page(session_id)
        if scroll_to_selector:
            await page.locator(scroll_to_selector).scroll_into_view_if_needed()
            await page.wait_for_timeout(500)
        img_bytes = await page.screenshot(full_page=full_page)
        return fastapi.Response(content=img_bytes, media_type="image/png")
    except Exception as e:
        return fastapi.Response(content=str(e), status_code=500)


@app.get("/page_info")
async def page_info(session: Optional[str] = fastapi.Query("default")):
    session_id = session or "default"
    try:
        page = await get_or_create_page(session_id)
        title = await page.title()
        url = page.url

        text_content = await page.evaluate("() => document.body ? document.body.innerText : ''")
        elements = await page.evaluate("""() => {
            return Array.from(document.querySelectorAll('a[href], button')).map(el => ({
                text: el.innerText.trim(),
                href: el.href || '',
                tag: el.tagName.toLowerCase()
            })).filter(el => el.text.length > 0);
        }""")
        return {
            "title": title,
            "url": url,
            "text_length": len(text_content),
            "excerpt": text_content[:500],
            "interactive_elements": elements[:20]
        }
    except Exception as e:
        return fastapi.Response(content=str(e), status_code=500)


@app.post("/click")
async def click_button(req: ClickButtonRequest, session: Optional[str] = fastapi.Query(None)):
    session_id = session or req.session or "default"
    try:
        page = await get_or_create_page(session_id)
        await page.click(req.selector)
        await page.wait_for_load_state("networkidle")
        return {"status": "success"}
    except Exception as e:
        return fastapi.Response(content=str(e), status_code=500)


@app.post("/api_request")
async def api_request(req: ApiRequest):
    try:
        check_url(req.url)
    except BlockedURL as e:
        raise fastapi.HTTPException(status_code=403, detail=str(e))

    current_url = req.url
    method = req.method
    data = req.data
    headers = dict(req.headers or {})

    async with httpx.AsyncClient(follow_redirects=False) as client:
        for hop in range(6):  # initial request + up to 5 redirects
            try:
                response = await client.request(
                    method=method,
                    url=current_url,
                    headers=headers,
                    json=data if method in ("POST", "PUT", "PATCH") else None,
                )
            except Exception as e:
                return fastapi.Response(content=str(e), status_code=500)

            if response.is_redirect:
                location = response.headers.get("location")
                if not location:
                    break
                next_url = urllib.parse.urljoin(current_url, location)
                try:
                    check_url(next_url)
                except BlockedURL as e:
                    raise fastapi.HTTPException(status_code=403, detail=str(e))

                current_url = next_url
                if response.status_code in (301, 302, 303):
                    method = "GET"
                    data = None
            else:
                break
        else:
            raise fastapi.HTTPException(status_code=400, detail="Too many redirects")

        return {"status_code": response.status_code, "content": response.text}


@app.get("/ddg_search")
async def ddg_search(query: str, max_results: int = 5):
    try:
        results = list(DDGS().text(query, max_results=max_results))
        return {"status": "success", "results": results}
    except Exception as e:
        return fastapi.Response(content=str(e), status_code=500)


if __name__ == "__main__":
    uvicorn.run("runtime_server:app", host="127.0.0.1", port=8059, reload=False)
