"""Live tests for gateway paid calls through real per-vendor proxies (ALGO, mUSD, subscription, errors)."""

import os
import time
import json
import base64
import asyncio
import subprocess
from typing import Dict, Any, Tuple
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app import chain, config
from algosdk import account, transaction, encoding
from algosdk.v2client import algod, indexer
from ai_economy_sdk import DefaultAvmSigner, sign_identity_txn, network_from_algod
from x402 import x402Client
from x402_algorand.exact.register import register_exact_avm_client
from x402.http.utils import decode_payment_required_header, encode_payment_signature_header

client = TestClient(app)

pytestmark = pytest.mark.skipif(
    os.environ.get("LOCALNET") != "1",
    reason="Paid live tests require LOCALNET=1"
)

REPO_ROOT = Path(__file__).resolve().parents[3]
DOMAINCTL = str(REPO_ROOT / "servers" / "tools" / "domainctl.sh")


def wait_and_up_domain(domain: str, max_wait: float = 1800.0):
    start = time.time()
    while time.time() - start < max_wait:
        res = subprocess.run([DOMAINCTL, "status", domain], capture_output=True, text=True)
        if "open" in res.stdout:
            time.sleep(10)
        else:
            break
    time.sleep(1.5)
    env = dict(os.environ, PAYMENTS="on")
    subprocess.run([DOMAINCTL, "up", domain], env=env, check=True)


def down_domain(domain: str):
    subprocess.run([DOMAINCTL, "down", domain], check=True)


@pytest.fixture(scope="module", autouse=True)
def manage_live_paid_services():
    """Start tts and sandbox_mcp in PAYMENTS=on mode, tear down when done."""
    wait_and_up_domain("tts")
    wait_and_up_domain("sandbox_mcp")
    try:
        yield
    finally:
        down_domain("tts")
        down_domain("sandbox_mcp")


def create_funded_payer(algod_c: algod.AlgodClient) -> Tuple[str, str]:
    """Create a brand new payer account funded with 10 ALGO via /api/faucet."""
    sk, addr = account.generate_account()
    resp = client.post("/api/faucet", json={"address": addr})
    assert resp.status_code == 200, f"Faucet failed for {addr}: {resp.text}"
    data = resp.json()
    assert data.get("ok") is True

    # Confirm on-chain balance >= 10 ALGO (10_000_000 microAlgos)
    info = algod_c.account_info(addr)
    bal = info.get("amount", 0)
    assert bal >= 10_000_000, f"Payer balance expected >= 10_000_000, got {bal}"
    return sk, addr


def opt_in_asset(algod_c: algod.AlgodClient, sk: str, addr: str, asset_id: int):
    sp = algod_c.suggested_params()
    txn = transaction.AssetTransferTxn(
        sender=addr,
        sp=sp,
        receiver=addr,
        amt=0,
        index=asset_id
    )
    stxn = txn.sign(sk)
    txid = algod_c.send_transaction(stxn)
    transaction.wait_for_confirmation(algod_c, txid, 4)


def get_asset_balance(algod_c: algod.AlgodClient, addr: str, asset_id: int) -> int:
    info = algod_c.account_info(addr)
    for a in info.get("assets", []):
        if a.get("asset-id") == asset_id:
            return a.get("amount", 0)
    return 0


def build_payment_signature(
    sk: str,
    header_b64: str,
    algod_url: str = "http://127.0.0.1:4001",
    algod_token: str = "a" * 64,
) -> str:
    """Build payment header in Python with x402 Python client."""
    pr = decode_payment_required_header(header_b64)
    algod_c = algod.AlgodClient(algod_token, algod_url)
    network = network_from_algod(algod_c)
    signer = DefaultAvmSigner(sk, algod_client=algod_c)
    xclient = x402Client()
    if pr.accepts:
        allowed = []
        for req in pr.accepts:
            req_asset = str(req.asset)
            if req_asset != "0":
                allowed.append({
                    "network": req.network or network,
                    "asset": req_asset,
                    "max_amount_per_payment": str(max(int(req.amount), 10_000_000)),
                })
        if allowed:
            xclient.set_spend_controls({"allowed_assets": allowed})

    register_exact_avm_client(
        xclient,
        signer,
        networks=network,
        algod_url=algod_url,
        algod_token=algod_token,
    )

    async def _create():
        return await xclient.create_payment_payload(pr)

    payload = asyncio.run(_create())
    return encode_payment_signature_header(payload)


# Module-level dictionary to pass state across dependent tests (e.g. history, replay)
_SHARED_STATE: Dict[str, Any] = {}


def test_algo_listing_tts1_vendorA():
    """
    1. ALGO listing (tts-1, vendorA):
       call without payment -> 402 with accepts[0].payTo == vendorA, amount == listing price;
       pay -> 200, result not isError, payment.txid on chain, receiver vendorA,
       payer -= price exactly, vendorA += price-2000.
    """
    algod_c = chain.get_algod_client()
    accounts_cfg = config.load_accounts()
    vendorA_addr = accounts_cfg["accounts"]["vendorA"]["address"]

    sk_payer, addr_payer = create_funded_payer(algod_c)

    payer_bal_before = algod_c.account_info(addr_payer)["amount"]
    vendorA_bal_before = algod_c.account_info(vendorA_addr)["amount"]

    # 1. Call without payment -> 402
    req_unpaid = {
        "tool": "synthesize_speech",
        "args": {"text": "Hello ALGO paid test 1"}
    }
    resp402 = client.post("/api/listings/tts-1/call", json=req_unpaid)
    assert resp402.status_code == 402, f"Expected 402, got {resp402.status_code}: {resp402.text}"
    body402 = resp402.json()
    assert body402.get("status") == 402
    pr = body402.get("paymentRequired", {})
    accepts = pr.get("accepts", [])
    assert len(accepts) > 0
    requirement = accepts[0]
    assert requirement.get("payTo") == vendorA_addr
    assert requirement.get("amount") == 20000 or requirement.get("amount") == "20000"
    header_b64 = body402.get("header")
    assert header_b64 is not None

    # 2. Build payment header in Python with x402 client
    payment_sig = build_payment_signature(sk_payer, header_b64)
    assert payment_sig is not None

    # 3. Call with paymentSignature -> 200
    req_paid = {
        "tool": "synthesize_speech",
        "args": {"text": "Hello ALGO paid test 1"},
        "paymentSignature": payment_sig
    }
    resp200 = client.post("/api/listings/tts-1/call", json=req_paid)
    assert resp200.status_code == 200, f"Expected 200, got {resp200.status_code}: {resp200.text}"
    data200 = resp200.json()

    assert data200.get("status") == 200
    result = data200.get("result", {})
    assert result.get("isError") is False
    payment = data200.get("payment", {})
    txid = payment.get("txid")
    assert txid is not None

    # 4. Confirm transaction on chain and verify receiver
    txinfo = algod_c.pending_transaction_info(txid)
    assert txinfo.get("confirmed-round", 0) > 0
    ptxn = txinfo.get("txn", {}).get("txn", {})
    assert ptxn.get("rcv") == vendorA_addr

    # 5. Verify balance deltas
    payer_bal_after = algod_c.account_info(addr_payer)["amount"]
    vendorA_bal_after = algod_c.account_info(vendorA_addr)["amount"]

    payer_delta = payer_bal_after - payer_bal_before
    vendorA_delta = vendorA_bal_after - vendorA_bal_before

    print(f"\n[TEST 1 ALGO DELTAS]")
    print(f"Payer before={payer_bal_before}, after={payer_bal_after}, delta={payer_delta} microAlgos")
    print(f"VendorA before={vendorA_bal_before}, after={vendorA_bal_after}, delta={vendorA_delta} microAlgos")

    # payer -= price exactly (20000)
    assert payer_delta == -20000, f"Expected payer delta -20000, got {payer_delta}"
    # vendorA += price - 2000 (18000)
    assert vendorA_delta == 18000, f"Expected vendorA delta +18000, got {vendorA_delta}"

    # Save to shared state for history and replay tests
    _SHARED_STATE["txid1"] = txid
    _SHARED_STATE["payer1"] = addr_payer
    _SHARED_STATE["payment_sig1"] = payment_sig


def test_musd_listing_tts2_vendorB():
    """
    2. mUSD listing (tts-2, vendorB):
       payer opted into mUSD and given 50 mUSD; 402 asset == mUSD id; pay -> 200;
       payer mUSD -= price, vendorB mUSD += price, vendorB ALGO -= 2000 (fee payer).
    """
    algod_c = chain.get_algod_client()
    accounts_cfg = config.load_accounts()
    vendorB_addr = accounts_cfg["accounts"]["vendorB"]["address"]
    musd_id = config.get_assets().get("mUSD", 3456)

    sk_payer, addr_payer = create_funded_payer(algod_c)

    # Opt payer into mUSD
    opt_in_asset(algod_c, sk_payer, addr_payer, musd_id)
    assert get_asset_balance(algod_c, addr_payer, musd_id) == 0

    # Transfer 50 mUSD (50_000_000 micro-mUSD) from server (treasury) to payer
    server_sk = chain.get_server_key()
    server_addr = chain.get_server_address()
    sp = algod_c.suggested_params()
    axfer_txn = transaction.AssetTransferTxn(
        sender=server_addr,
        sp=sp,
        receiver=addr_payer,
        amt=50_000_000,
        index=musd_id
    )
    stxn = axfer_txn.sign(server_sk)
    txid = algod_c.send_transaction(stxn)
    transaction.wait_for_confirmation(algod_c, txid, 4)
    assert get_asset_balance(algod_c, addr_payer, musd_id) == 50_000_000

    # Balances before
    payer_musd_before = get_asset_balance(algod_c, addr_payer, musd_id)
    vendorB_musd_before = get_asset_balance(algod_c, vendorB_addr, musd_id)
    vendorB_algo_before = algod_c.account_info(vendorB_addr)["amount"]

    # 1. Call without payment -> 402
    req_unpaid = {
        "tool": "synthesize_speech",
        "args": {"text": "Hello mUSD paid test 2"}
    }
    resp402 = client.post("/api/listings/tts-2/call", json=req_unpaid)
    assert resp402.status_code == 402, f"Expected 402, got {resp402.status_code}: {resp402.text}"
    body402 = resp402.json()
    assert body402.get("status") == 402
    pr = body402.get("paymentRequired", {})
    accepts = pr.get("accepts", [])
    assert len(accepts) > 0
    requirement = accepts[0]
    assert requirement.get("payTo") == vendorB_addr
    # asset == mUSD id (3456)
    req_asset = requirement.get("asset")
    assert str(req_asset) == str(musd_id) or req_asset == "mUSD"
    price = int(requirement.get("amount", 16000))
    header_b64 = body402.get("header")
    assert header_b64 is not None

    # 2. Build payment header in Python with x402 client
    payment_sig = build_payment_signature(sk_payer, header_b64)
    assert payment_sig is not None

    # 3. Call with paymentSignature -> 200
    req_paid = {
        "tool": "synthesize_speech",
        "args": {"text": "Hello mUSD paid test 2"},
        "paymentSignature": payment_sig
    }
    resp200 = client.post("/api/listings/tts-2/call", json=req_paid)
    assert resp200.status_code == 200, f"Expected 200, got {resp200.status_code}: {resp200.text}"
    data200 = resp200.json()

    assert data200.get("status") == 200
    result = data200.get("result", {})
    assert result.get("isError") is False
    payment = data200.get("payment", {})
    txid2 = payment.get("txid")
    assert txid2 is not None

    # 4. Confirm on-chain
    txinfo = algod_c.pending_transaction_info(txid2)
    assert txinfo.get("confirmed-round", 0) > 0

    # 5. Verify balance deltas
    payer_musd_after = get_asset_balance(algod_c, addr_payer, musd_id)
    vendorB_musd_after = get_asset_balance(algod_c, vendorB_addr, musd_id)
    vendorB_algo_after = algod_c.account_info(vendorB_addr)["amount"]

    payer_musd_delta = payer_musd_after - payer_musd_before
    vendorB_musd_delta = vendorB_musd_after - vendorB_musd_before
    vendorB_algo_delta = vendorB_algo_after - vendorB_algo_before

    print(f"\n[TEST 2 mUSD DELTAS]")
    print(f"Payer mUSD before={payer_musd_before}, after={payer_musd_after}, delta={payer_musd_delta}")
    print(f"VendorB mUSD before={vendorB_musd_before}, after={vendorB_musd_after}, delta={vendorB_musd_delta}")
    print(f"VendorB ALGO before={vendorB_algo_before}, after={vendorB_algo_after}, delta={vendorB_algo_delta}")

    # payer mUSD -= price (16000)
    assert payer_musd_delta == -price, f"Expected payer mUSD delta -{price}, got {payer_musd_delta}"
    # vendorB mUSD += price (16000)
    assert vendorB_musd_delta == price, f"Expected vendorB mUSD delta +{price}, got {vendorB_musd_delta}"
    # vendorB ALGO -= 2000 (fee payer)
    assert vendorB_algo_delta == -2000, f"Expected vendorB ALGO delta -2000, got {vendorB_algo_delta}"

    # Save to shared state for history
    _SHARED_STATE["txid2"] = txid2
    _SHARED_STATE["payer2"] = addr_payer


def test_tool_error_not_charged():
    """
    3. Tool error not charged: sandbox listing, language "cobol", paid ->
       result isError true, payment.txid null, balances unchanged.
    """
    algod_c = chain.get_algod_client()
    accounts_cfg = config.load_accounts()
    vendorA_addr = accounts_cfg["accounts"]["vendorA"]["address"]

    sk_payer, addr_payer = create_funded_payer(algod_c)

    payer_bal_before = algod_c.account_info(addr_payer)["amount"]
    vendorA_bal_before = algod_c.account_info(vendorA_addr)["amount"]

    # 1. Call without payment -> 402 on sandbox_mcp-1
    req_unpaid = {
        "tool": "run_sandbox_code",
        "args": {"language": "cobol", "code": "DISPLAY 1."}
    }
    resp402 = client.post("/api/listings/sandbox_mcp-1/call", json=req_unpaid)
    assert resp402.status_code == 402, f"Expected 402, got {resp402.status_code}: {resp402.text}"
    body402 = resp402.json()
    header_b64 = body402.get("header")
    assert header_b64 is not None

    # 2. Build payment header in Python with x402 client
    payment_sig = build_payment_signature(sk_payer, header_b64)
    assert payment_sig is not None

    # 3. Call with paymentSignature -> result isError true, payment.txid null
    req_paid = {
        "tool": "run_sandbox_code",
        "args": {"language": "cobol", "code": "DISPLAY 1."},
        "paymentSignature": payment_sig
    }
    resp200 = client.post("/api/listings/sandbox_mcp-1/call", json=req_paid)
    assert resp200.status_code == 200, f"Expected 200, got {resp200.status_code}: {resp200.text}"
    data200 = resp200.json()

    assert data200.get("status") == 200
    result = data200.get("result", {})
    assert result.get("isError") is True, f"Expected isError True, got {result.get('isError')}"
    payment = data200.get("payment", {})
    assert payment.get("txid") is None, f"Expected payment.txid null, got {payment.get('txid')}"

    # 4. Verify balances unchanged
    payer_bal_after = algod_c.account_info(addr_payer)["amount"]
    vendorA_bal_after = algod_c.account_info(vendorA_addr)["amount"]

    payer_delta = payer_bal_after - payer_bal_before
    vendorA_delta = vendorA_bal_after - vendorA_bal_before

    print(f"\n[TEST 3 TOOL ERROR DELTAS]")
    print(f"Payer before={payer_bal_before}, after={payer_bal_after}, delta={payer_delta} microAlgos")
    print(f"VendorA before={vendorA_bal_before}, after={vendorA_bal_after}, delta={vendorA_delta} microAlgos")

    assert payer_delta == 0, f"Expected payer balance unchanged (delta 0), got {payer_delta}"
    assert vendorA_delta == 0, f"Expected vendorA balance unchanged (delta 0), got {vendorA_delta}"


def _buy_pass(algod_c, sk, addr, scope):
    """Buy a pass exactly like the browser: gateway quote -> wallet signs -> submit to algod. Returns the quote."""
    r = client.post("/api/passes/quote", json={"address": addr, "scope": scope})
    assert r.status_code == 200, f"quote failed: {r.text}"
    q = r.json()
    stxn = encoding.msgpack_decode(q["txn"]).sign(sk)
    txid = algod_c.send_transaction(stxn)
    from algosdk import transaction as _tx
    _tx.wait_for_confirmation(algod_c, txid, 10)
    idx_c = chain.get_indexer_client()
    deadline = time.time() + 20
    while time.time() < deadline:
        try:
            if idx_c.search_transactions(txid=txid).get("transactions"):
                return q
        except Exception:
            pass
        time.sleep(0.5)
    raise AssertionError("indexer did not index the pass purchase within 20 s")


def _call_with_identity(algod_c, sk, listing_id, tool, args):
    sp = algod_c.suggested_params()
    ident = sign_identity_txn(sk, sp.gh)["X-Identity-Txn"]
    return client.post(f"/api/listings/{listing_id}/call", json={"tool": tool, "args": args, "identityTxn": ident})


def test_pass_is_individual_per_vendor_and_service():
    """
    A pass belongs to ONE vendor. A service pass covers that one service, a vendor pass covers that vendor's catalogue.
      1. buy the service pass for tts-3 (Quarry Compute) -> tts-3 is free with a wallet identity proof
      2. same wallet, same tool: tts-1 (Nova Labs), tts-2 (Blue Fern) and tts-4 (Lumen Works) still ask for payment (402)
      3. Quarry's OTHER service sandbox_mcp-3 still asks for payment (402): a service pass is not a vendor pass
      4. without the identity proof, tts-3 asks for payment (402)
      5. buy the vendor pass for Quarry -> sandbox_mcp-3 is free now, tts-1 is still 402
    """
    algod_c = chain.get_algod_client()
    sk, addr = create_funded_payer(algod_c)
    m = config.load_marketplace()
    tts_args = {"text": "pass scope test"}

    q = _buy_pass(algod_c, sk, addr, "listing:tts-3")
    assert q["vendor"]["id"] == "vendorC" and q["kind"] == "service"

    before = algod_c.account_info(addr)["amount"]
    r = _call_with_identity(algod_c, sk, "tts-3", "synthesize_speech", tts_args)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == 200 and body["result"]["isError"] is False and body["payment"]["txid"] is None
    assert algod_c.account_info(addr)["amount"] == before, "a pass call must cost nothing"

    for other in ("tts-1", "tts-2", "tts-4"):
        r = _call_with_identity(algod_c, sk, other, "synthesize_speech", tts_args)
        assert r.status_code == 402, f"{other} must still ask for payment, got {r.status_code}"

    sandbox_args = {"code": "print(1)", "language": "python"}
    r = _call_with_identity(algod_c, sk, "sandbox_mcp-3", "run_sandbox_code", sandbox_args)
    assert r.status_code == 402, f"a service pass must not unlock the vendor's other service, got {r.status_code}"

    r = client.post("/api/listings/tts-3/call", json={"tool": "synthesize_speech", "args": tts_args})
    assert r.status_code == 402, "without the identity proof the pass cannot be used"

    vq = _buy_pass(algod_c, sk, addr, "vendor:vendorC")
    assert vq["vendor"]["id"] == "vendorC" and vq["kind"] == "vendor" and vq["price"] == m["vendors"]["vendorC"]["pass"]["price"]
    r = _call_with_identity(algod_c, sk, "sandbox_mcp-3", "run_sandbox_code", sandbox_args)
    assert r.status_code == 200 and r.json()["payment"]["txid"] is None, r.text
    r = _call_with_identity(algod_c, sk, "tts-1", "synthesize_speech", tts_args)
    assert r.status_code == 402, "Quarry's vendor pass must not unlock Nova Labs"

    mine = client.get(f"/api/passes/{addr}").json()
    assert {p["scope"] for p in mine} == {"listing:tts-3", "vendor:vendorC"}
