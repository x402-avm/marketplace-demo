"""FastAPI backend application for the AI Service Marketplace Gateway."""

import asyncio
import base64
import json
import logging
import time
from contextlib import asynccontextmanager
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, UploadFile, File, Query, Path, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import algosdk.encoding

from app import config, chain, db, mcp_relay, catalog, files, faucet, passes, history, explorer


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    config.load_accounts()
    config.load_marketplace()
    yield


logger = logging.getLogger("gateway.main")

app = FastAPI(title="AI Service Marketplace Gateway", version="1.0.0", lifespan=lifespan)

# CORS middleware for React web frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MAX_CALL_BODY_BYTES = 1 * 1024 * 1024  # 1 MB


@app.middleware("http")
async def limit_call_body_size(request: Request, call_next):
    path = request.url.path
    if request.method == "POST" and path.startswith("/api/listings/") and path.endswith("/call"):
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > MAX_CALL_BODY_BYTES:
                    return JSONResponse(
                        status_code=413,
                        content={"detail": "request body too large, max 1 MB"}
                    )
            except ValueError:
                pass

        body = await request.body()
        if len(body) > MAX_CALL_BODY_BYTES:
            return JSONResponse(
                status_code=413,
                content={"detail": "request body too large, max 1 MB"}
            )
    return await call_next(request)


# ---------------------------------------------------------
# Health & Configuration
# ---------------------------------------------------------

@app.get("/api/health")
def health_check():
    try:
        status = chain.get_algod_client().status()
        return {"ok": True, "round": status.get("last-round", 0)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/api/config")
def get_config():
    """Return public marketplace configuration. Private keys/mnemonics are NEVER exposed."""
    return config.get_public_config()


# ---------------------------------------------------------
# Vendors
# ---------------------------------------------------------

@app.get("/api/vendors")
def get_vendors():
    m = config.load_marketplace()
    vendors_dict = m.get("vendors", {})
    listings = m.get("listings", [])
    assets = config.get_assets()
    musd_id = assets.get("mUSD")
    indexer_c = chain.get_indexer_client()

    listing_counts: Dict[str, int] = {}
    for l in listings:
        v = l.get("vendor")
        if v:
            listing_counts[v] = listing_counts.get(v, 0) + 1

    result = []
    for v_id, v_info in vendors_dict.items():
        addr = v_info.get("address", "")
        earnings = {"ALGO": 0, "mUSD": 0}
        if addr:
            try:
                for prefix in (b"x402-payment", b"x402-pass:"):
                    tx_res = indexer_c.search_transactions(
                        address=addr,
                        address_role="receiver",
                        note_prefix=prefix
                    )
                    for t in tx_res.get("transactions", []):
                        ttype = t.get("tx-type")
                        if ttype == "pay":
                            earnings["ALGO"] += t.get("payment-transaction", {}).get("amount", 0)
                        elif ttype == "axfer":
                            ax = t.get("asset-transfer-transaction", {})
                            if ax.get("asset-id") == musd_id:
                                earnings["mUSD"] += ax.get("amount", 0)
            except Exception:
                pass

        result.append({
            "id": v_id,
            "name": v_info.get("name", v_id),
            "address": addr,
            "listings": listing_counts.get(v_id, 0),
            "domains": sorted({l["domain"] for l in listings if l.get("vendor") == v_id}),
            "asset": v_info.get("asset", "ALGO"),
            "pass": v_info.get("pass"),
            "earnings": earnings
        })
    return result


# ---------------------------------------------------------
# Listings & Tool Calls
# ---------------------------------------------------------

@app.get("/api/listings")
async def list_listings(domain: Optional[str] = None):
    return await catalog.get_all_listings(domain=domain)


@app.get("/api/listings/{listing_id}")
async def get_listing(listing_id: str):
    res = await catalog.get_listing_by_id(listing_id)
    if not res:
        raise HTTPException(status_code=404, detail=f"listing '{listing_id}' not found")
    return res


class ToolCallRequest(BaseModel):
    tool: str
    args: Dict[str, Any] = {}
    paymentSignature: Optional[str] = None
    identityTxn: Optional[str] = None


@app.post("/api/listings/{listing_id}/call")
async def call_listing_tool(listing_id: str, req: ToolCallRequest):
    m = config.load_marketplace()
    raw_listings = m.get("listings", [])
    target = None
    for item in raw_listings:
        if item.get("id") == listing_id:
            target = item
            break

    if not target:
        raise HTTPException(status_code=404, detail=f"listing '{listing_id}' not found")

    port = target.get("port")
    if not port:
        raise HTTPException(status_code=500, detail="listing has no port configured")

    domain = target.get("domain", "")
    timeout = mcp_relay.get_domain_timeout(domain)

    extra_headers: Dict[str, str] = {}
    if req.paymentSignature:
        extra_headers["PAYMENT-SIGNATURE"] = req.paymentSignature
    if req.identityTxn:
        extra_headers["X-Identity-Txn"] = req.identityTxn

    try:
        status, payload = await mcp_relay.call_tool_on_port(
            port=port,
            name=req.tool,
            arguments=req.args,
            extra_headers=extra_headers,
            timeout=timeout
        )
    except mcp_relay.McpRelayTimeoutError:
        raise HTTPException(status_code=504, detail="service timed out")
    except mcp_relay.McpRelayError as e:
        if "invalid endpoint" in str(e):
            logger.error("Proxy for listing %s sent an invalid endpoint: %s", listing_id, e)
            raise HTTPException(status_code=502, detail="proxy sent an invalid endpoint")
        raise HTTPException(status_code=502, detail=f"relay connection error: {e}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"relay connection error: {e}")

    # 402 Payment Required response
    if status == "402":
        pr_header = payload or ""
        pr_json = {}
        if pr_header:
            try:
                pr_json = json.loads(base64.b64decode(pr_header).decode("utf-8"))
            except Exception:
                pr_json = {}
        return JSONResponse(status_code=402, content={
            "status": 402,
            "paymentRequired": pr_json,
            "header": pr_header
        })

    # Error status from relay
    if status == "error":
        raise HTTPException(status_code=502, detail=str(payload))

    # Success (200 / 202) -> payload is result dict
    result_dict = payload
    txid: Optional[str] = None
    amount: int = 0
    asset: str = target.get("asset", "ALGO")
    pay_to: str = ""
    caller_addr: Optional[str] = None
    is_err = result_dict.get("isError", False)

    if req.paymentSignature:
        try:
            sig_data = json.loads(base64.b64decode(req.paymentSignature).decode("utf-8"))
            accepted = sig_data.get("accepted", {})
            amount = int(accepted.get("amount", 0))
            asset = accepted.get("asset", asset)
            pay_to = accepted.get("payTo", "")

            pay_payload = sig_data.get("payload", {})
            pg = pay_payload.get("paymentGroup", [])
            idx = pay_payload.get("paymentIndex", 1)
            if idx < len(pg):
                stxn_b64 = pg[idx]
                stxn_obj = algosdk.encoding.msgpack_decode(stxn_b64)
                computed_txid = stxn_obj.get_txid()
                caller_addr = getattr(stxn_obj.transaction, "sender", None)

                # Poll algod pending_transaction_info up to 10s to confirm it is on chain
                # If tool returned error, settlement was aborted and not submitted to chain
                if not is_err:
                    algod_c = chain.get_algod_client()
                    confirmed_on_chain = False
                    start_poll = time.time()
                    while time.time() - start_poll < 10.0:
                        try:
                            info = algod_c.pending_transaction_info(computed_txid)
                            if info.get("confirmed-round", 0) > 0:
                                confirmed_on_chain = True
                                break
                        except Exception:
                            pass
                        await asyncio.sleep(0.5)

                    if confirmed_on_chain:
                        txid = computed_txid
                    else:
                        # Fallback check indexer
                        try:
                            idx_res = chain.get_indexer_client().search_transactions(txid=computed_txid)
                            if idx_res.get("transactions"):
                                txid = computed_txid
                        except Exception:
                            pass
        except Exception:
            pass
    elif req.identityTxn:
        try:
            itxn_obj = algosdk.encoding.msgpack_decode(req.identityTxn)
            caller_addr = getattr(itxn_obj.transaction, "sender", None)
        except Exception:
            pass

    # Log every call in SQLite
    db.log_call(
        listing_id=listing_id,
        tool=req.tool,
        address=caller_addr,
        txid=txid,
        amount=amount,
        asset=asset,
        is_error=is_err
    )

    return {
        "status": 200,
        "result": result_dict,
        "payment": {
            "txid": txid,
            "amount": amount,
            "asset": asset,
            "payTo": pay_to
        }
    }


# ---------------------------------------------------------
# Files & Uploads
# ---------------------------------------------------------

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    saved_path = await files.save_uploaded_file(file)
    return {"path": saved_path}


@app.get("/api/files")
def get_file(path: str = Query(..., description="Absolute path to file")):
    return files.serve_file(path)


# ---------------------------------------------------------
# Faucet
# ---------------------------------------------------------

class FaucetRequest(BaseModel):
    address: str


@app.post("/api/faucet")
def request_faucet(body: FaucetRequest):
    if faucet.is_blocked_address(body.address):
        raise HTTPException(
            status_code=400,
            detail="treasury, vendor, and dispenser addresses cannot use faucet"
        )
    return faucet.dispense(body.address)


# ---------------------------------------------------------
# Passes (individual: one service, or one vendor's whole catalogue)
# ---------------------------------------------------------

class PassQuoteRequest(BaseModel):
    address: str
    scope: str


@app.post("/api/passes/quote")
def quote_pass(body: PassQuoteRequest):
    return passes.create_quote(body.address, body.scope)


@app.get("/api/passes/{address}")
def my_passes(address: str):
    return passes.list_passes(address)


# ---------------------------------------------------------
# History
# ---------------------------------------------------------

@app.get("/api/history/{address}")
def get_history(address: str):
    return history.get_user_history(address)


# ---------------------------------------------------------
# Explorer
# ---------------------------------------------------------

@app.get("/api/explorer/blocks")
def get_blocks(limit: int = Query(20, ge=1, le=100)):
    return explorer.get_recent_blocks(limit=limit)


@app.get("/api/explorer/block/{round_num}")
def get_block(round_num: int = Path(..., ge=0)):
    return explorer.get_block_details(round_num)


@app.get("/api/explorer/tx/{txid}")
def get_tx(txid: str):
    return explorer.get_transaction(txid)


@app.get("/api/explorer/verify")
def verify_blocks(
    from_round: Optional[int] = Query(None, alias="from", ge=0),
    to_round: Optional[int] = Query(None, alias="to", ge=0)
):
    if from_round is not None and to_round is not None:
        if to_round < from_round or (to_round - from_round) > 1000:
            raise HTTPException(
                status_code=422,
                detail="invalid range: to must be >= from and (to - from) <= 1000"
            )
    return explorer.verify_chain(from_round=from_round, to_round=to_round)
