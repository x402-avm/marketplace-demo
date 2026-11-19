import os
import uuid
import gc
import sys
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
import httpx

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs")
os.makedirs(OUT_DIR, exist_ok=True)

mcp = FastMCP("Kokoro TTS")

@mcp.tool()
async def synthesize_speech(text: str, voice: str = "af_heart") -> str:
    """Synthesize speech using Kokoro TTS."""
    if len(text) > 1000:
        raise ToolError("Error: Text exceeds 1000 character limit.")
        
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post("http://127.0.0.1:8050/tts", json={"text": text, "voice": voice}, timeout=60.0)
        except Exception as e:
            raise ToolError(f"Error connecting to runtime server: {str(e)}")
            
    if response.status_code == 200:
        filename = os.path.join(OUT_DIR, f"speech_p{os.getpid()}_{uuid.uuid4().hex[:8]}.wav")
        with open(filename, "wb") as f:
            f.write(response.content)
            
        del response
        gc.collect()
        return f"Speech synthesized successfully. Saved to {filename}"
    else:
        raise ToolError(f"Error: {response.text}")
