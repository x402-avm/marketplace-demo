"""Unified serving layer for MCP server fleet: free (plain SSE) or payment-gated with x402."""
import json
import os
from pathlib import Path

SERVERS = Path(__file__).resolve().parents[1]
REPO = SERVERS.parent


def proxy_port(domain: str, index: int) -> int:
    """Get the port for a proxy from topology.json, or PORT env override."""
    if "PORT" in os.environ:
        return int(os.environ["PORT"])
    topology = json.load(open(SERVERS / "topology.json"))
    return topology[domain]["proxy_ports"][index - 1]


def serve(mcp, domain: str, index: int) -> None:
    """Serve an MCP instance either free (plain SSE) or payment-gated via x402."""
    port = proxy_port(domain, index)
    mode = os.environ.get("PAYMENTS", "off").lower()
    print(f"[{domain} proxy {index}] port {port} payments={mode}", flush=True)

    if mode == "on" and os.environ.get("FAST_TEST_MODE") == "1":
        import sys
        print(
            f"[{domain} proxy {index}] REFUSING to serve paid mode with FAST_TEST_MODE=1 (placeholder output must never be billed)",
            file=sys.stderr,
            flush=True,
        )
        sys.exit(3)

    if mode != "on":
        mcp.run(transport="sse", host="127.0.0.1", port=port)
        return

    cfg = json.load(open(REPO / "chain" / "accounts.json"))
    pricing = json.load(open(SERVERS / "pricing.json"))
    prices = pricing["domains"].get(domain, {})

    from algosdk import mnemonic
    import algosdk.v2client.algod
    import inspect
    import uvicorn
    from ai_economy_sdk import PaymentGate, DefaultAvmSigner, ChainReader

    algod = algosdk.v2client.algod.AlgodClient(cfg["algod_token"], cfg["algod_url"])

    mp_path = Path(os.environ.get("MARKETPLACE_JSON", SERVERS / "marketplace.json"))
    listing = None
    mp = None
    if mp_path.exists():
        try:
            mp = json.loads(mp_path.read_text())
            for item in mp.get("listings", []):
                if item.get("domain") == domain and item.get("proxy_index") == index:
                    listing = item
                    break
        except Exception:
            listing = None

    if listing and mp:
        vendor_name = listing["vendor"]
        vendor_acc = cfg["accounts"][vendor_name]
        vendor_pk = mnemonic.to_private_key(vendor_acc["mnemonic"])
        signer = DefaultAvmSigner(vendor_pk, algod_client=algod)
        pay_to = vendor_acc["address"]
        asset_id = mp["assets"][listing["asset"]]
        prices = listing.get("prices", {})
        min_price = pricing.get("minimum", 3000)
        default_price = max(min_price, round(pricing["default"] * listing["multiplier"]))
        # Passes are individual: only a receipt for THIS service or for THIS vendor's whole catalogue makes calls free
        # here. The old global AI-SUB token is not honoured by marketplace listings.
        vendor_meta = mp["vendors"][vendor_name]
        pass_scopes = {
            listing["pass"]["scope"]: int(listing["pass"]["price"]),
            vendor_meta["pass"]["scope"]: int(vendor_meta["pass"]["price"]),
        }

        gate_kwargs = dict(
            signer=signer,
            network=cfg["network"],
            pay_to=pay_to,
            asset_id=asset_id,
            prices=prices,
            default_price=default_price,
            chain=ChainReader(indexer_url=cfg["indexer_url"]),
            pass_scopes=pass_scopes,
            pass_days=float(mp.get("passes", {}).get("days", 30)),
            bulk_threshold=1_000_000,
            bulk_discount=0.5,
            replay_db=str(SERVERS / "tests" / "run" / f"replay_{domain}.sqlite"),
        )

        print(f"[{domain} proxy {index}] listing {listing['id']} vendor {listing['vendor']} asset {listing['asset']} pay_to {pay_to[:8]}...", flush=True)
        gate = PaymentGate(**gate_kwargs)
    else:
        server_pk = mnemonic.to_private_key(cfg["accounts"]["server"]["mnemonic"])
        signer = DefaultAvmSigner(server_pk, algod_client=algod)
        gate = PaymentGate(
            signer=signer,
            network=cfg["network"],
            pay_to=cfg["accounts"]["server"]["address"],
            asset_id=0,
            prices=prices,
            default_price=pricing["default"],
            chain=ChainReader(indexer_url=cfg["indexer_url"]),
            subscription_asset_id=cfg["subscription_asset_id"],
            bulk_threshold=1_000_000,
            bulk_discount=0.5,
            replay_db=str(SERVERS / "tests" / "run" / f"replay_{domain}.sqlite"),
        )
    uvicorn.run(gate.wrap(mcp, transport="sse"), host="127.0.0.1", port=port, log_level="warning")
