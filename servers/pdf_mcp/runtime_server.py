import asyncio
from fastapi import FastAPI, HTTPException, Request
import uvicorn
from pydantic import BaseModel
from typing import Dict, Any, Optional

from pdf_mcp import mcp

app = FastAPI()

class ToolCallRequest(BaseModel):
    name: str
    arguments: Optional[Dict[str, Any]] = None

from fastapi.responses import JSONResponse

@app.get("/tools")
async def list_tools():
    tools = await mcp.list_tools()
    result = []
    for t in tools:
        if hasattr(t, "model_dump"):
            result.append(t.model_dump())
        else:
            result.append({
                "name": getattr(t, "name", str(t)),
                "description": getattr(t, "description", ""),
                "inputSchema": getattr(t, "inputSchema", {})
            })
    # Remove ellipsis or pydantic v2 artifacts if any
    import json
    def clean_dict(d):
        if isinstance(d, dict):
            return {k: clean_dict(v) for k, v in d.items() if v is not ...}
        if isinstance(d, (list, tuple, set)):
            return [clean_dict(v) for v in d]
        if isinstance(d, (int, float, str, bool, type(None))):
            return d
        return str(d)
    
    return JSONResponse(clean_dict(result))

@app.post("/call")
async def call_tool_endpoint(req: ToolCallRequest):
    try:
        result = await mcp.call_tool(req.name, req.arguments or {})
        
        content = []
        for item in getattr(result, "content", []):
            if hasattr(item, "model_dump"):
                content.append(item.model_dump())
            elif hasattr(item, "dict"):
                content.append(item.dict())
            else:
                content.append(item)
                
        return {"content": content, "isError": getattr(result, "isError", getattr(result, "is_error", False))}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8105)
