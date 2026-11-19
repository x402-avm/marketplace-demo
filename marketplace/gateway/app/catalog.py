"""Catalog management for marketplace listings and MCP tools."""

import time
import asyncio
from typing import Dict, Any, List, Optional, Tuple

from app import config
from app import mcp_relay

# Cache for MCP tools: port -> (timestamp, is_online, tools_list)
_TOOL_CACHE: Dict[int, Tuple[float, bool, List[Dict[str, Any]]]] = {}
CACHE_TTL = 60.0


async def get_tools_for_listing(
    port: int,
    prices: Dict[str, int],
    default_price: int
) -> Tuple[bool, List[Dict[str, Any]]]:
    now = time.time()
    cached = _TOOL_CACHE.get(port)
    if cached and (now - cached[0] < CACHE_TTL):
        _, is_online, raw_tools = cached
        processed = _format_tools_with_prices(raw_tools, prices, default_price)
        return is_online, processed

    # Try to connect and list tools
    try:
        raw_tools = await mcp_relay.list_tools_on_port(port, timeout=3.0)
        _TOOL_CACHE[port] = (now, True, raw_tools)
        return True, _format_tools_with_prices(raw_tools, prices, default_price)
    except Exception:
        # Port is closed or unreachable
        prev_tools = cached[2] if cached else []
        _TOOL_CACHE[port] = (now, False, prev_tools)
        return False, _format_tools_with_prices(prev_tools, prices, default_price)


def _format_tools_with_prices(
    tools: List[Dict[str, Any]],
    prices: Dict[str, int],
    default_price: int
) -> List[Dict[str, Any]]:
    formatted = []
    for t in tools:
        name = t.get("name", "")
        price = prices.get(name, default_price)
        formatted.append({
            "name": name,
            "description": t.get("description", ""),
            "inputSchema": t.get("inputSchema", {}),
            "price": price,
        })
    return formatted


async def get_all_listings(domain: Optional[str] = None) -> List[Dict[str, Any]]:
    m = config.load_marketplace()
    raw_listings = m.get("listings", [])
    vendors = m.get("vendors", {})

    if domain:
        raw_listings = [item for item in raw_listings if item.get("domain") == domain]

    tasks = []
    for item in raw_listings:
        port = item.get("port", 0)
        prices = item.get("prices", {})
        default_price = item.get("default_price", 3000)
        tasks.append(get_tools_for_listing(port, prices, default_price))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    listings = []
    for item, res in zip(raw_listings, results):
        if isinstance(res, Exception):
            online, tools = False, []
        else:
            online, tools = res

        v_id = item.get("vendor", "")
        v_info = vendors.get(v_id, {})
        vendor_obj = {
            "id": v_id,
            "name": v_info.get("name", v_id),
            "address": v_info.get("address", "")
        }

        listings.append({
            "id": item.get("id"),
            "domain": item.get("domain"),
            "vendor": vendor_obj,
            "asset": item.get("asset", "ALGO"),
            "port": item.get("port"),
            "online": online,
            "tools": tools,
            "prices": item.get("prices", {}),
            "pass": item.get("pass"),
        })
    return listings


async def get_listing_by_id(listing_id: str) -> Optional[Dict[str, Any]]:
    m = config.load_marketplace()
    raw_listings = m.get("listings", [])
    target = None
    for item in raw_listings:
        if item.get("id") == listing_id:
            target = item
            break
    if not target:
        return None

    vendors = m.get("vendors", {})
    port = target.get("port", 0)
    prices = target.get("prices", {})
    default_price = target.get("default_price", 3000)

    try:
        online, tools = await get_tools_for_listing(port, prices, default_price)
    except Exception:
        online, tools = False, []

    v_id = target.get("vendor", "")
    v_info = vendors.get(v_id, {})
    vendor_obj = {
        "id": v_id,
        "name": v_info.get("name", v_id),
        "address": v_info.get("address", "")
    }

    return {
        "id": target.get("id"),
        "domain": target.get("domain"),
        "vendor": vendor_obj,
        "asset": target.get("asset", "ALGO"),
        "port": target.get("port"),
        "online": online,
        "tools": tools,
        "prices": target.get("prices", {}),
        "pass": target.get("pass"),
    }
