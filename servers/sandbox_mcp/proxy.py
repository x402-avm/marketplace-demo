from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
import httpx

mcp = FastMCP("Code Sandbox")

@mcp.tool()
def run_sandbox_code(code: str, language: str) -> str:
    """Run code in a sandbox using the runtime server."""
    try:
        response = httpx.post("http://127.0.0.1:8081/run", json={"code": code, "language": language}, timeout=40)
    except Exception as e:
        raise ToolError(f"Error connecting to runtime server: {e}")

    if response.status_code != 200:
        detail = None
        try:
            detail = response.json().get("detail")
        except Exception:
            detail = response.text
        raise ToolError(f"Error: {detail or response.text}")

    data = response.json()
    stdout = data.get("stdout", "")
    stderr = data.get("stderr", "")

    if "Unsupported language" in stderr:
        raise ToolError(f"Error: {stderr}")

    return f"Stdout:\n{stdout}\nStderr:\n{stderr}"
