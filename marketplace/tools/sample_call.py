#!/usr/bin/env python3
"""Make one real, paid tool call against a running marketplace listing and print the result.

    .venv/bin/python marketplace/tools/sample_call.py <listing-id> <tool> '<json args>'
    .venv/bin/python marketplace/tools/sample_call.py tts-1 synthesize_speech '{"text": "hello"}'
    .venv/bin/python marketplace/tools/sample_call.py --list tts-1        # tools and input schemas

Pays from the LocalNet test account `client1` (chain/accounts.json). LocalNet only.
Prints JSON: {"isError": bool, "content": [...]} so a UI can be designed around the real output.
"""
import asyncio
import json
import sys
from pathlib import Path

from algosdk import mnemonic

from ai_economy_sdk.client import paid_mcp_session

REPO = Path(__file__).resolve().parents[2]


def _listing(listing_id: str) -> dict:
    mp = json.loads((REPO / "servers" / "marketplace.json").read_text())
    for item in mp["listings"]:
        if item["id"] == listing_id:
            return item
    sys.exit(f"no listing {listing_id!r} in servers/marketplace.json")


async def main() -> None:
    args = sys.argv[1:]
    if len(args) < 2 and not (len(args) == 2 and args[0] == "--list"):
        sys.exit(__doc__)
    acc = json.loads((REPO / "chain" / "accounts.json").read_text())
    key = mnemonic.to_private_key(acc["accounts"]["client1"]["mnemonic"])
    listing_id = args[1] if args[0] == "--list" else args[0]
    item = _listing(listing_id)
    url = f"http://127.0.0.1:{item['port']}/sse"
    async with paid_mcp_session(url, key, acc["network"], acc["algod_url"], acc["algod_token"], timeout=900, transport="sse") as session:
        if args[0] == "--list":
            tools = await session.list_tools()
            print(json.dumps([{"name": t.name, "description": t.description, "inputSchema": t.inputSchema} for t in tools.tools], indent=2))
            return
        tool = args[1]
        call_args = json.loads(args[2]) if len(args) > 2 else {}
        res = await session.call_tool(tool, call_args)
        content = [c.model_dump(exclude_none=True) for c in res.content]
        print(json.dumps({"isError": bool(res.isError), "content": content}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
