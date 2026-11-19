"""Block explorer backend reusing logic from chain/explorer.py."""

import base64
import hashlib
from typing import Dict, Any, List, Optional
from fastapi import HTTPException
import msgpack
import algosdk.encoding

from app import chain


def strip_blk(h: str) -> str:
    """Strip leading 'blk-' from a block or prev hash string."""
    if not h or h == "-":
        return "-"
    return str(h).removeprefix("blk-")


def compute_header_hash_from_msgpack(raw_msgpack: bytes) -> str:
    """Recompute block hash = sha512_256(b'BH' + msgpack header)."""
    unpacked = msgpack.unpackb(raw_msgpack, strict_map_key=False)
    header_dict = dict(unpacked["block"])
    header_dict.pop("txns", None)
    header_bytes = base64.b64decode(algosdk.encoding.msgpack_encode(header_dict))
    h = hashlib.new("sha512_256", b"BH" + header_bytes).digest()
    return base64.b32encode(h).decode("utf-8").rstrip("=")


def get_recent_blocks(limit: int = 20) -> List[Dict[str, Any]]:
    algod_c = chain.get_algod_client()
    try:
        status = algod_c.status()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"algod unreachable: {e}")

    last_round = status.get("last-round", 0)
    start_round = max(1, last_round - limit + 1)
    rounds = list(range(last_round, start_round - 1, -1))

    blocks = []
    for r in rounds:
        try:
            h_resp = algod_c.algod_request("GET", f"/blocks/{r}/hash")
            bhash = strip_blk(h_resp.get("blockHash", "-"))
        except Exception:
            bhash = "-"

        try:
            binfo = algod_c.block_info(r)
            bdata = binfo.get("block", {}) if isinstance(binfo, dict) else {}
        except Exception:
            bdata = {}

        prev_hash = strip_blk(bdata.get("prev", "-"))
        time_ts = bdata.get("ts")
        tx_count = len(bdata.get("txns", []))

        blocks.append({
            "round": r,
            "hash": bhash,
            "prevHash": prev_hash,
            "time": time_ts,
            "txCount": tx_count
        })

    return blocks


def get_block_details(round_num: int) -> Dict[str, Any]:
    algod_c = chain.get_algod_client()
    indexer_c = chain.get_indexer_client()

    try:
        h_resp = algod_c.algod_request("GET", f"/blocks/{round_num}/hash")
        expected_hash = strip_blk(h_resp.get("blockHash", "-"))
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"block hash not found for round {round_num}: {e}")

    try:
        binfo = algod_c.block_info(round_num)
        bdata = binfo.get("block", {}) if isinstance(binfo, dict) else {}
        prev_hash = strip_blk(bdata.get("prev", "-"))
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"block {round_num} not found: {e}")

    # Recompute block hash using msgpack header
    hash_ok = False
    try:
        raw_msgpack = algod_c.block_info(round_num, response_format="msgpack")
        computed_hash = compute_header_hash_from_msgpack(raw_msgpack)
        hash_ok = (computed_hash == expected_hash)
    except Exception:
        hash_ok = False

    # Fetch transactions for block via indexer
    txns = []
    try:
        res = indexer_c.search_transactions(block=round_num)
        raw_txns = res.get("transactions", [])
        for t in raw_txns:
            tx_type = t.get("tx-type", "")
            snd = t.get("sender", "")
            rcv = None
            amt = 0
            asset = "ALGO"

            if tx_type == "pay":
                pay_info = t.get("payment-transaction", {})
                rcv = pay_info.get("receiver")
                amt = pay_info.get("amount", 0)
            elif tx_type == "axfer":
                axfer_info = t.get("asset-transfer-transaction", {})
                rcv = axfer_info.get("receiver")
                amt = axfer_info.get("amount", 0)
                asset = str(axfer_info.get("asset-id", "ASA"))

            note_raw = t.get("note")
            note_str = None
            if note_raw:
                try:
                    note_str = base64.b64decode(note_raw).decode("utf-8", errors="replace")
                except Exception:
                    note_str = note_raw

            txns.append({
                "txid": t.get("id"),
                "type": tx_type,
                "from": snd,
                "to": rcv,
                "amount": amt,
                "asset": asset,
                "fee": t.get("fee", 0),
                "note": note_str,
                "group": t.get("group")
            })
    except Exception:
        # Fallback to parsing algod block_data
        for raw_t in bdata.get("txns", []):
            td = raw_t.get("txn", {}) if isinstance(raw_t, dict) else {}
            txns.append({
                "txid": None,
                "type": td.get("type"),
                "from": td.get("snd"),
                "to": td.get("rcv") or td.get("arcv"),
                "amount": td.get("amt", td.get("aamt", 0)),
                "asset": "ALGO" if td.get("type") == "pay" else str(td.get("xaid", "ASA")),
                "fee": td.get("fee", 0),
                "note": str(td.get("note")),
                "group": str(td.get("grp")) if "grp" in td else None
            })

    return {
        "round": round_num,
        "hash": expected_hash,
        "prevHash": prev_hash,
        "hashOk": hash_ok,
        "txns": txns
    }


def get_transaction(txid: str) -> Dict[str, Any]:
    indexer_c = chain.get_indexer_client()
    try:
        res = indexer_c.transaction(txid)
        return res.get("transaction", res)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"transaction {txid} not found: {e}")


def verify_chain(from_round: Optional[int] = None, to_round: Optional[int] = None) -> Dict[str, Any]:
    algod_c = chain.get_algod_client()
    try:
        status = algod_c.status()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"algod unreachable: {e}")

    last_round = status.get("last-round", 0)
    to_r = to_round if to_round is not None else last_round
    from_r = from_round if from_round is not None else max(0, to_r - 50)

    checked = 0
    broken = []

    for r in range(from_r + 1, to_r + 1):
        try:
            binfo = algod_c.block_info(r)
            prev_raw = str(binfo.get("block", {}).get("prev", ""))
            prev_norm = strip_blk(prev_raw)

            h_resp = algod_c.algod_request("GET", f"/blocks/{r-1}/hash")
            hash_raw = str(h_resp.get("blockHash", ""))
            hash_norm = strip_blk(hash_raw)

            checked += 1
            if prev_norm != hash_norm:
                broken.append({
                    "round": r,
                    "blockPrev": prev_norm,
                    "expectedPrev": hash_norm
                })
        except Exception as e:
            broken.append({
                "round": r,
                "error": str(e)
            })

    return {
        "checked": checked,
        "broken": broken
    }
