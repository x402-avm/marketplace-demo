import asyncio
from mcp.client.sse import sse_client

async def main():
    async with sse_client("http://127.0.0.1:8077/sse") as streams:
        async with streams[0]:
            from mcp.client.session import ClientSession
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                print("Testing download_yt_video...")
                try:
                    result = await session.call_tool("download_yt_video", {"url": "https://www.youtube.com/watch?v=jNQXAC9IVRw"})
                    print(f"Result: {result.content[0].text[:200]}")
                except Exception as e:
                    print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
