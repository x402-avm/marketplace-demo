#!/usr/bin/env python3
"""
Generate servers/marketplace.json from chain/accounts.json, servers/topology.json, and servers/pricing.json.
Deterministic: sorts listings by (domain, proxy_index) with 2-space indented JSON.
Contains NO secrets.
"""

import json
from pathlib import Path
import sys
import ai_economy_sdk

REPO_DIR = Path(__file__).resolve().parents[1]
ACCOUNTS_FILE = REPO_DIR / "chain" / "accounts.json"
TOPOLOGY_FILE = REPO_DIR / "servers" / "topology.json"
PRICING_FILE = REPO_DIR / "servers" / "pricing.json"
OUTPUT_FILE = REPO_DIR / "servers" / "marketplace.json"

VENDOR_ORDER = ["vendorA", "vendorB", "vendorC", "vendorD"]
VENDOR_METADATA = {
    "vendorA": {"name": "Nova Labs", "multiplier": 1.0, "asset": "ALGO"},
    "vendorB": {"name": "Blue Fern AI", "multiplier": 0.8, "asset": "mUSD"},
    "vendorC": {"name": "Quarry Compute", "multiplier": 1.25, "asset": "ALGO"},
    "vendorD": {"name": "Lumen Works", "multiplier": 1.5, "asset": "ALGO"},
}


PASS_TOOL_MULTIPLE = 80       # a service pass costs 80 average calls of that service
PASS_VENDOR_SHARE = 0.6       # a vendor pass costs 60% of buying every one of that vendor's service passes
MIN_SERVICE_PASS = 100_000
PASS_ROUND = 10_000


def _round_up(value: float, step: int) -> int:
    return int(-(-value // step) * step)


def generate_marketplace_data() -> dict:
    if not ACCOUNTS_FILE.exists():
        raise FileNotFoundError(f"Accounts file not found: {ACCOUNTS_FILE}")
    if not TOPOLOGY_FILE.exists():
        raise FileNotFoundError(f"Topology file not found: {TOPOLOGY_FILE}")
    if not PRICING_FILE.exists():
        raise FileNotFoundError(f"Pricing file not found: {PRICING_FILE}")

    accounts_data = json.loads(ACCOUNTS_FILE.read_text(encoding="utf-8"))
    topology = json.loads(TOPOLOGY_FILE.read_text(encoding="utf-8"))
    pricing = json.loads(PRICING_FILE.read_text(encoding="utf-8"))

    network = ai_economy_sdk.resolve_network(accounts_data["network"])
    treasury_addr = accounts_data["accounts"]["server"]["address"]
    musd_id = int(accounts_data["musd_asset_id"])
    sub_id = int(accounts_data["subscription_asset_id"])

    assets = {
        "ALGO": 0,
        "mUSD": musd_id,
        "AI-SUB": sub_id,
    }

    # Passes are individual: a service pass covers one vendor's one service, a vendor pass covers all of that
    # vendor's services. Both are an ordinary payment to the vendor (in the vendor's asset) with the note
    # "x402-pass:<scope>"; nothing is shared between vendors.
    passes = {
        "days": 30,
        "note_prefix": "x402-pass:",
        "service_pass_tool_multiple": PASS_TOOL_MULTIPLE,
        "vendor_pass_share": PASS_VENDOR_SHARE,
        "min_service_pass": MIN_SERVICE_PASS,
    }

    vendors = {}
    for v in VENDOR_ORDER:
        vendors[v] = {
            "name": VENDOR_METADATA[v]["name"],
            "address": accounts_data["accounts"][v]["address"],
        }

    default_price = int(pricing.get("default", 3000))
    min_price = int(pricing.get("minimum", pricing.get("default", 3000)))

    listings = []
    # Sort domains alphabetically for deterministic order
    for domain in sorted(topology.keys()):
        domain_info = topology[domain]
        proxy_ports = domain_info.get("proxy_ports", [])
        domain_pricing = pricing.get("domains", {}).get(domain, {})

        for idx, port in enumerate(proxy_ports, start=1):
            vendor_key = VENDOR_ORDER[(idx - 1) % len(VENDOR_ORDER)]
            vmeta = VENDOR_METADATA[vendor_key]
            multiplier = vmeta["multiplier"]
            asset_name = vmeta["asset"]

            # Calculate prices for each tool in domain
            tool_prices = {}
            for tool_name in sorted(domain_pricing.keys()):
                base = int(domain_pricing[tool_name])
                comp = round(base * multiplier)
                tool_prices[tool_name] = max(comp, min_price)

            avg_tool = sum(tool_prices.values()) / len(tool_prices) if tool_prices else default_price
            service_pass = max(MIN_SERVICE_PASS, _round_up(PASS_TOOL_MULTIPLE * avg_tool, PASS_ROUND))

            listing = {
                "id": f"{domain}-{idx}",
                "domain": domain,
                "proxy_index": idx,
                "port": int(port),
                "vendor": vendor_key,
                "asset": asset_name,
                "multiplier": multiplier,
                "prices": tool_prices,
                "pass": {"scope": f"listing:{domain}-{idx}", "price": service_pass},
            }
            listings.append(listing)

    # Sort listings by domain, then proxy_index
    listings.sort(key=lambda item: (item["domain"], item["proxy_index"]))

    for v in VENDOR_ORDER:
        total = sum(l["pass"]["price"] for l in listings if l["vendor"] == v)
        vendors[v]["asset"] = VENDOR_METADATA[v]["asset"]
        vendors[v]["pass"] = {"scope": f"vendor:{v}", "price": _round_up(PASS_VENDOR_SHARE * total, PASS_ROUND)}

    return {
        "network": network,
        "assets": assets,
        "treasury": treasury_addr,
        "passes": passes,
        "vendors": vendors,
        "listings": listings,
    }


def main():
    data = generate_marketplace_data()
    json_text = json.dumps(data, indent=2) + "\n"
    OUTPUT_FILE.write_text(json_text, encoding="utf-8")
    print(f"Generated {OUTPUT_FILE} with {len(data['listings'])} listings.")


if __name__ == "__main__":
    main()
