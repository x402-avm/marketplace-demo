"""Individual passes: a pass is a payment to ONE vendor with the note "x402-pass:<scope>".

Scopes:
  listing:<id>     one vendor's one service (e.g. listing:tts-1)
  vendor:<vendor>  every service of one vendor (e.g. vendor:vendorA)

The gateway only builds the unsigned payment (the buyer signs and submits it from the browser) and reads receipts back
from the indexer. It never signs, co-signs or holds anything. Each vendor's own gate honours only its own receipts.
"""

import base64
from typing import Any, Dict, List, Optional, Tuple

from algosdk import transaction
from algosdk.encoding import is_valid_address, msgpack_encode
from fastapi import HTTPException

from ai_economy_sdk import ChainReader, PASS_NOTE_PREFIX

from app import chain, config


def _marketplace() -> Dict[str, Any]:
    return config.load_marketplace()


def _asset_id(asset_name: str) -> int:
    return int(config.get_assets().get(asset_name, 0))


def resolve_scope(scope: str) -> Dict[str, Any]:
    """Validate a scope string against marketplace.json and return what the buyer would be paying for."""
    m = _marketplace()
    vendors = m.get("vendors", {})
    days = int(m.get("passes", {}).get("days", 30))
    if scope.startswith("listing:"):
        lid = scope[len("listing:"):]
        item = next((l for l in m.get("listings", []) if l.get("id") == lid), None)
        if not item or "pass" not in item:
            raise HTTPException(status_code=404, detail=f"no pass is sold for '{scope}'")
        vendor_id = item["vendor"]
        price = int(item["pass"]["price"])
        asset_name = item.get("asset", "ALGO")
        label = f"{item['domain']} from {vendors.get(vendor_id, {}).get('name', vendor_id)}"
        kind = "service"
    elif scope.startswith("vendor:"):
        vendor_id = scope[len("vendor:"):]
        v = vendors.get(vendor_id)
        if not v or "pass" not in v:
            raise HTTPException(status_code=404, detail=f"no pass is sold for '{scope}'")
        price = int(v["pass"]["price"])
        asset_name = v.get("asset", "ALGO")
        label = f"everything from {v.get('name', vendor_id)}"
        kind = "vendor"
    else:
        raise HTTPException(status_code=400, detail="scope must be listing:<id> or vendor:<vendor>")
    v = vendors[vendor_id]
    return {
        "scope": scope,
        "kind": kind,
        "label": label,
        "price": price,
        "asset": asset_name,
        "assetId": _asset_id(asset_name),
        "days": days,
        "vendor": {"id": vendor_id, "name": v.get("name", vendor_id), "address": v.get("address", "")},
    }


def create_quote(address: str, scope: str) -> Dict[str, Any]:
    if not address or not is_valid_address(address):
        raise HTTPException(status_code=400, detail="invalid Algorand address")
    info = resolve_scope(scope)
    algod_c = chain.get_algod_client()
    try:
        acc = algod_c.account_info(address)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"could not read the account from algod: {e}")

    sp = algod_c.suggested_params()
    fee = sp.min_fee or 1000
    if info["assetId"] == 0:
        spendable = acc.get("amount", 0) - acc.get("min-balance", 100_000)
        if spendable < info["price"] + fee:
            raise HTTPException(status_code=400, detail="not enough ALGO for this pass; use the faucet on the Wallet page")
    else:
        holding = next((a for a in acc.get("assets", []) if a.get("asset-id") == info["assetId"]), None)
        if holding is None:
            raise HTTPException(status_code=400, detail=f"opt in to {info['asset']} first")
        if holding.get("amount", 0) < info["price"]:
            raise HTTPException(status_code=400, detail=f"not enough {info['asset']} for this pass")
        if acc.get("amount", 0) - acc.get("min-balance", 100_000) < fee:
            raise HTTPException(status_code=400, detail="not enough ALGO to pay the network fee")

    note = f"{PASS_NOTE_PREFIX}{scope}".encode()
    receiver = info["vendor"]["address"]
    if info["assetId"] == 0:
        txn = transaction.PaymentTxn(sender=address, sp=sp, receiver=receiver, amt=info["price"], note=note)
    else:
        txn = transaction.AssetTransferTxn(
            sender=address, sp=sp, receiver=receiver, amt=info["price"], index=info["assetId"], note=note
        )
    return {**info, "fee": fee, "txn": msgpack_encode(txn), "signIndexes": [0]}


def _vendor_scopes(vendor_id: str) -> Dict[str, int]:
    m = _marketplace()
    scopes = {l["pass"]["scope"]: int(l["pass"]["price"]) for l in m.get("listings", []) if l.get("vendor") == vendor_id and "pass" in l}
    v = m.get("vendors", {}).get(vendor_id, {})
    if "pass" in v:
        scopes[v["pass"]["scope"]] = int(v["pass"]["price"])
    return scopes


def list_passes(address: str) -> List[Dict[str, Any]]:
    if not address or not is_valid_address(address):
        raise HTTPException(status_code=400, detail="invalid Algorand address")
    m = _marketplace()
    days = float(m.get("passes", {}).get("days", 30))
    reader = ChainReader(indexer_url=config.get_indexer_url())
    listings = {l["id"]: l for l in m.get("listings", [])}
    out: List[Dict[str, Any]] = []
    for vendor_id, v in m.get("vendors", {}).items():
        asset_name = v.get("asset", "ALGO")
        receipts = reader.active_passes(address, v.get("address", ""), _asset_id(asset_name), _vendor_scopes(vendor_id), days)
        for r in receipts:
            scope = r["scope"]
            item: Dict[str, Any] = {
                "scope": scope,
                "kind": "vendor" if scope.startswith("vendor:") else "service",
                "vendor": {"id": vendor_id, "name": v.get("name", vendor_id)},
                "asset": asset_name,
                "amount": r["amount"],
                "txid": r["txid"],
                "purchasedAt": int(r["round_time"]),
                "expiresAt": int(r["expires"]),
            }
            if scope.startswith("listing:"):
                lst = listings.get(scope[len("listing:"):])
                if lst:
                    item["listing"] = {"id": lst["id"], "domain": lst["domain"]}
            out.append(item)
    out.sort(key=lambda p: p["purchasedAt"], reverse=True)
    return out
