import contextlib
import os
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession

import shutil
from pathlib import Path

rust_binary_path = os.environ.get("PDF_READER_MCP_BINARY") or shutil.which("pdf-reader-mcp-server") or str(Path(__file__).resolve().parent / "bin" / "pdf-reader-mcp-server")

class MCPManager:
    def __init__(self):
        self.session = None
        self.exit_stack = contextlib.AsyncExitStack()
    
    async def connect(self):
        params = StdioServerParameters(
            command=rust_binary_path,
            args=[]
        )
        read, write = await self.exit_stack.enter_async_context(stdio_client(params))
        self.session = await self.exit_stack.enter_async_context(ClientSession(read, write))
        await self.session.initialize()
    
    async def disconnect(self):
        await self.exit_stack.aclose()

manager = MCPManager()
app = FastAPI()

@app.on_event("startup")
async def startup():
    if os.path.exists(rust_binary_path):
        await manager.connect()
    else:
        print(f"Warning: Rust binary not found at {rust_binary_path}")

@app.on_event("shutdown")
async def shutdown():
    await manager.disconnect()

@app.post("/call_tool/{tool_name}")
async def call_tool(tool_name: str, request: Request):
    args = await request.json()
    if not manager.session:
        raise HTTPException(status_code=500, detail="MCP Rust Server not connected")
    try:
        result = await manager.session.call_tool(tool_name, arguments=args)
        return {
            "content": [c.model_dump() if hasattr(c, 'model_dump') else c.dict() for c in result.content],
            "isError": getattr(result, "isError", False)
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        from mcp.shared.exceptions import McpError
        if isinstance(e, McpError):
            return {
                "content": [{"type": "text", "text": f"McpError: {e.error.message}"}],
                "isError": True
            }
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8111)
