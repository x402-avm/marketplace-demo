import asyncio
from mcp import ClientSession
from mcp.client.sse import sse_client
import json

async def run_wiki_test(url, selector, api_url):
    mcp_url = "http://127.0.0.1:8057/sse"
    print(f"\n--- Testing on {url} ---")
    async with sse_client(mcp_url) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            
            # 1. Open Page
            res = await session.call_tool("web_open_page", {"url": url})
            print(f"Open Page Output: {res.content[0].text}")
            
            # 2. Page Info
            res = await session.call_tool("web_page_info", {})
            try:
                info = json.loads(res.content[0].text)
                print(f"Page Title: {info.get('title')}")
                print(f"Text Length: {info.get('text_length')} characters")
                print(f"Excerpt: {info.get('excerpt')[:150].replace(chr(10), ' ')}...")
                links = info.get('interactive_elements', [])
                print(f"Found {len(links)} interactive elements. First 3:")
                for l in links[:3]:
                    print(f"  - [{l['tag']}] {l['text']} -> {l['href']}")
            except Exception as e:
                print(f"Page Info Output error: {e}, Raw: {res.content[0].text[:200]}")
            
            # 3. Screenshots
            filename1 = f"{url.split('/')[-1]}_screenshot_top.png"
            res1 = await session.call_tool("web_screen_shoot", {"filename": filename1, "full_page": False})
            print(f"Screenshot 1 (Top) Output: {res1.content[0].text}")
            
            filename2 = f"{url.split('/')[-1]}_screenshot_refs.png"
            res2 = await session.call_tool("web_screen_shoot", {"filename": filename2, "full_page": False, "scroll_to_selector": "#References"})
            print(f"Screenshot 2 (References) Output: {res2.content[0].text}")
            
            # 4. API Request
            res = await session.call_tool("send_api_request", {"url": api_url})
            try:
                api_info = json.loads(res.content[0].text)
                print(f"API Request Status: {api_info.get('status_code')}")
                print(f"API Content snippet: {str(api_info.get('content'))[:100].replace(chr(10), ' ')}...")
            except:
                print(f"API Output: {res.content[0].text[:200]}")
            
            # 5. Click Button
            res = await session.call_tool("web_click_button", {"selector": selector})
            print(f"Click Button Output: {res.content[0].text}")

async def main():
    await run_wiki_test(
        "https://en.wikipedia.org/wiki/Quantum_computing",
        "#vector-main-menu-dropdown",
        "https://en.wikipedia.org/api/rest_v1/page/summary/Quantum_computing"
    )
    await run_wiki_test(
        "https://en.wikipedia.org/wiki/Albert_Einstein",
        "#vector-main-menu-dropdown", 
        "https://en.wikipedia.org/api/rest_v1/page/summary/Albert_Einstein"
    )

if __name__ == "__main__":
    asyncio.run(main())
