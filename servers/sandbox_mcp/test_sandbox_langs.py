import asyncio
from mcp.client.sse import sse_client

async def main():
    async with sse_client("http://127.0.0.1:8081/sse") as streams:
        async with streams[0]:
            from mcp.client.session import ClientSession
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                
                codes = {
                    "javascript": "console.log('Hello from JS');",
                    "java": "public class Main { public static void main(String[] args) { System.out.println(\"Hello from Java\"); } }",
                    "c": "#include <stdio.h>\\nint main() { printf(\"Hello from C\\\\n\"); return 0; }",
                    "cpp": "#include <iostream>\\nint main() { std::cout << \"Hello from C++\" << std::endl; return 0; }"
                }
                
                for lang, code in codes.items():
                    print(f"Testing {lang}...")
                    try:
                        result = await session.call_tool("run_sandbox_code", {"language": lang, "code": code})
                        print(f"Result for {lang}: {result.content[0].text[:100].strip()}")
                    except Exception as e:
                        print(f"Error for {lang}: {e}")

if __name__ == "__main__":
    asyncio.run(main())
