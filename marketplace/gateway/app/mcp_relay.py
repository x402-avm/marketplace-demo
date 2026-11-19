"""Raw MCP-over-SSE client using httpx."""

import json
import urllib.parse
from typing import Dict, Any, List, Tuple, Optional
import httpx



class McpRelayError(Exception):
    pass


class McpRelayTimeoutError(McpRelayError):
    pass


DOMAIN_TIMEOUTS: Dict[str, float] = {
    "image_gen": 900.0,
    "video_edit_mcp": 300.0,
    "conversion_mcp": 300.0,
}
DEFAULT_TIMEOUT: float = 120.0


def get_domain_timeout(domain: str) -> float:
    return DOMAIN_TIMEOUTS.get(domain, DEFAULT_TIMEOUT)


class McpSseClient:
    def __init__(self, port: int, timeout: float = 120.0):
        self.port = port
        self.base_url = f"http://127.0.0.1:{port}"
        self.sse_url = f"{self.base_url}/sse"
        self.timeout = httpx.Timeout(timeout, connect=10.0, read=min(timeout, 60.0))
        self.client: Optional[httpx.AsyncClient] = None
        self.stream_ctx = None
        self.stream = None
        self.lines_iter = None
        self.post_url: Optional[str] = None
        self.req_id: int = 0

    async def __aenter__(self):
        self.client = httpx.AsyncClient(timeout=self.timeout)
        try:
            self.stream_ctx = self.client.stream("GET", self.sse_url)
            self.stream = await self.stream_ctx.__aenter__()
            self.lines_iter = self.stream.aiter_lines()

            # First event: endpoint
            endpoint = None
            async for line in self.lines_iter:
                line_str = line.strip()
                if line_str.startswith("data:"):
                    endpoint = line_str.split(":", 1)[1].strip()
                    break

            if not endpoint:
                raise McpRelayError("Failed to receive endpoint from SSE stream")

            self.post_url = urllib.parse.urljoin(self.sse_url, endpoint)

            # Strict SSRF validation on resolved post_url
            parsed = urllib.parse.urlparse(self.post_url)
            if (
                parsed.scheme != "http"
                or parsed.hostname not in ("127.0.0.1", "localhost")
                or parsed.port != self.port
                or not parsed.path.startswith("/messages")
            ):
                raise McpRelayError("proxy sent an invalid endpoint")

            # Handshake: initialize
            self.req_id += 1
            init_req = {
                "jsonrpc": "2.0",
                "id": self.req_id,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "marketplace-gateway", "version": "1.0.0"}
                }
            }
            init_resp = await self.client.post(self.post_url, json=init_req)
            if init_resp.status_code not in (200, 202):
                raise McpRelayError(f"Initialize failed with status {init_resp.status_code}: {init_resp.text}")

            init_result = await self._read_response_for_id(self.req_id)
            if "error" in init_result:
                raise McpRelayError(f"Initialize RPC error: {init_result['error']}")

            # Post notifications/initialized
            notif = {"jsonrpc": "2.0", "method": "notifications/initialized"}
            await self.client.post(self.post_url, json=notif)

            return self
        except httpx.TimeoutException:
            await self.close()
            raise McpRelayTimeoutError("service timed out")
        except Exception:
            await self.close()
            raise

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def close(self):
        if self.stream_ctx:
            try:
                await self.stream_ctx.__aexit__(None, None, None)
            except Exception:
                pass
            self.stream_ctx = None
        if self.client:
            try:
                await self.client.aclose()
            except Exception:
                pass
            self.client = None

    async def _read_response_for_id(self, target_id: int) -> Dict[str, Any]:
        """Read SSE events until a JSON-RPC message with target_id is received."""
        if not self.lines_iter:
            raise McpRelayError("SSE stream not open")

        async for line in self.lines_iter:
            line_str = line.strip()
            if line_str.startswith("data:"):
                payload_str = line_str.split(":", 1)[1].strip()
                try:
                    data = json.loads(payload_str)
                    if isinstance(data, dict) and data.get("id") == target_id:
                        return data
                except Exception:
                    continue
        raise McpRelayError(f"SSE stream closed before receiving response for id {target_id}")

    async def list_tools(self) -> List[Dict[str, Any]]:
        self.req_id += 1
        req = {
            "jsonrpc": "2.0",
            "id": self.req_id,
            "method": "tools/list",
            "params": {}
        }
        resp = await self.client.post(self.post_url, json=req)
        if resp.status_code not in (200, 202):
            raise McpRelayError(f"tools/list failed with status {resp.status_code}: {resp.text}")

        data = await self._read_response_for_id(self.req_id)
        if "error" in data:
            raise McpRelayError(f"tools/list RPC error: {data['error']}")
        return data.get("result", {}).get("tools", [])

    async def call_tool(
        self,
        name: str,
        arguments: Dict[str, Any],
        extra_headers: Optional[Dict[str, str]] = None
    ) -> Tuple[str, Any]:
        """
        Call a tool.
        Returns:
            ("402", payment_required_header_str) if 402 Payment Required
            ("ok", result_dict) if successful (status 200/202)
            ("error", error_message) on other failures
        """
        self.req_id += 1
        req = {
            "jsonrpc": "2.0",
            "id": self.req_id,
            "method": "tools/call",
            "params": {
                "name": name,
                "arguments": arguments
            }
        }
        headers = {}
        if extra_headers:
            headers.update(extra_headers)

        resp = await self.client.post(self.post_url, json=req, headers=headers)
        if resp.status_code == 402:
            # Payment required
            pr_hdr = resp.headers.get("payment-required") or resp.headers.get("PAYMENT-REQUIRED") or ""
            return ("402", pr_hdr)

        if resp.status_code in (200, 202):
            data = await self._read_response_for_id(self.req_id)
            if "error" in data:
                err = data["error"]
                msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
                return ("ok", {
                    "content": [{"type": "text", "text": msg}],
                    "isError": True
                })
            res = data.get("result", {})
            return ("ok", res)

        return ("error", f"Tool call failed with HTTP status {resp.status_code}: {resp.text}")


async def list_tools_on_port(port: int, timeout: float = 10.0) -> List[Dict[str, Any]]:
    async with McpSseClient(port, timeout=timeout) as client:
        return await client.list_tools()


async def call_tool_on_port(
    port: int,
    name: str,
    arguments: Dict[str, Any],
    extra_headers: Optional[Dict[str, str]] = None,
    timeout: float = DEFAULT_TIMEOUT
) -> Tuple[str, Any]:
    try:
        async with McpSseClient(port, timeout=timeout) as client:
            return await client.call_tool(name, arguments, extra_headers)
    except httpx.TimeoutException:
        raise McpRelayTimeoutError("service timed out")
