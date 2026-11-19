"""Transaction payment history joined with gateway call logs."""

import base64
from typing import Dict, Any, List
from algosdk.encoding import is_valid_address
from fastapi import HTTPException

from app import chain, config, db


def get_user_history(address: str) -> List[Dict[str, Any]]:
    if not address or not is_valid_address(address):
        raise HTTPException(status_code=400, detail="invalid Algorand address")

    indexer_c = chain.get_indexer_client()
    m = config.load_marketplace()
    vendors = m.get("vendors", {})
    assets = config.get_assets()
    musd_id = assets.get("mUSD")

    # Map vendor address -> vendor name/id
    vendor_by_addr = {}
    for v_id, v_info in vendors.items():
        v_addr = v_info.get("address")
        if v_addr:
            vendor_by_addr[v_addr] = v_info.get("name", v_id)

    # Local SQLite calls by address
    local_calls = db.get_calls_by_address(address, limit=100)
    call_by_txid = {c["txid"]: c for c in local_calls if c.get("txid")}

    txns = []
    for prefix in (b"x402-payment", b"x402-pass:"):
        try:
            res = indexer_c.search_transactions(
                address=address,
                address_role="sender",
                note_prefix=prefix
            )
            txns.extend(res.get("transactions", []))
        except Exception:
            # If the indexer fails, fall back to local database records
            continue

    history = []
    seen_txids = set()

    for t in txns:
        txid = t.get("id")
        if not txid:
            continue
        seen_txids.add(txid)

        tx_type = t.get("tx-type", "")
        to_addr = None
        amount = 0
        asset = "ALGO"

        if tx_type == "pay":
            pay_info = t.get("payment-transaction", {})
            to_addr = pay_info.get("receiver")
            amount = pay_info.get("amount", 0)
            asset = "ALGO"
        elif tx_type == "axfer":
            axfer_info = t.get("asset-transfer-transaction", {})
            to_addr = axfer_info.get("receiver")
            amount = axfer_info.get("amount", 0)
            asset_id = axfer_info.get("asset-id")
            asset = "mUSD" if asset_id == musd_id else str(asset_id)

        vendor_name = vendor_by_addr.get(to_addr, "Unknown Vendor")

        # Join with calls.sqlite
        call_rec = call_by_txid.get(txid) or db.get_call_by_txid(txid)
        listing = call_rec.get("listing_id") if call_rec else None
        tool = call_rec.get("tool") if call_rec else None

        scope = None
        try:
            note = base64.b64decode(t.get("note", "")).decode()
            if note.startswith("x402-pass:"):
                scope = note[len("x402-pass:"):]
        except Exception:
            pass

        entry = {
            "txid": txid,
            "round": t.get("confirmed-round"),
            "time": t.get("round-time"),
            "amount": amount,
            "asset": asset,
            "to": to_addr,
            "vendor": vendor_name,
            "kind": "pass" if scope else "call",
            "listing": listing,
            "tool": tool,
        }
        if scope:
            entry["scope"] = scope
        history.append(entry)

    # Also include any local call records that may have confirmed txids
    for c in local_calls:
        ctxid = c.get("txid")
        if ctxid and ctxid not in seen_txids:
            history.append({
                "txid": ctxid,
                "round": None,
                "time": int(c.get("ts", 0)),
                "amount": c.get("amount", 0),
                "asset": c.get("asset", "ALGO"),
                "to": None,
                "vendor": "Local Call",
                "listing": c.get("listing_id"),
                "tool": c.get("tool"),
            })

    history.sort(key=lambda h: h.get("time") or 0, reverse=True)
    return history
