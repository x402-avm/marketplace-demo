"""Live test suite for marketplace gateway (requires LOCALNET=1 and live LocalNet)."""

import os
import subprocess
import json
import base64
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app import chain, config
from algosdk import account, mnemonic, encoding

client = TestClient(app)

pytestmark = pytest.mark.skipif(
    os.environ.get("LOCALNET") != "1",
    reason="Live tests require LOCALNET=1"
)


@pytest.fixture(scope="module", autouse=True)
def manage_live_services():
    """Start tts domain for live testing and tear down when finished."""
    repo_root = Path(__file__).resolve().parents[3]
    domainctl = str(repo_root / "servers" / "tools" / "domainctl.sh")
    subprocess.run([domainctl, "up", "tts"], check=True)
    try:
        yield
    finally:
        subprocess.run([domainctl, "down", "tts"], check=True)


def test_live_listings_and_tts_online():
    """Verify /api/listings reflects live tts proxy on port 8051 with online=True and tools."""
    resp = client.get("/api/listings?domain=tts")
    assert resp.status_code == 200
    listings = resp.json()
    assert len(listings) >= 1

    tts1 = next((item for item in listings if item["id"] == "tts-1"), None)
    assert tts1 is not None, "Listing tts-1 not found"
    assert tts1["port"] == 8051
    assert tts1["online"] is True, f"tts-1 expected online=True, got {tts1['online']}"

    tool_names = [t["name"] for t in tts1.get("tools", [])]
    assert "synthesize_speech" in tool_names, f"synthesize_speech missing in {tool_names}"


def test_live_free_proxy_call():
    """Verify /api/listings/tts-1/call executes against live tts proxy and returns valid audio output."""
    payload = {
        "tool": "synthesize_speech",
        "args": {
            "text": "Algorand AI service marketplace live check",
            "voice": "af_heart"
        }
    }
    resp = client.post("/api/listings/tts-1/call", json=payload)
    assert resp.status_code == 200, f"Call failed: {resp.text}"
    data = resp.json()

    assert data["status"] == 200
    result = data["result"]
    assert result.get("isError") is False
    content = result.get("content", [])
    assert len(content) > 0
    text_out = content[0].get("text", "")
    assert "speech synthesized successfully" in text_out.lower()

    # Free call has 0 paid
    payment = data["payment"]
    assert payment["amount"] == 0
    assert payment["txid"] is None


def test_live_explorer_verify_last_50_rounds():
    """Verify hash-chain integrity on the last 50 blocks: broken must be empty."""
    algod_c = chain.get_algod_client()
    status = algod_c.status()
    last_round = status.get("last-round", 0)
    from_round = max(0, last_round - 50)

    resp = client.get(f"/api/explorer/verify?from={from_round}&to={last_round}")
    assert resp.status_code == 200
    data = resp.json()

    assert data["checked"] >= 50
    assert data["broken"] == [], f"Hash chain broken at: {data['broken']}"


def test_live_faucet_to_new_address():
    """Verify /api/faucet transfers exactly 10 ALGO to a fresh Algorand account."""
    _, new_addr = account.generate_account()
    algod_c = chain.get_algod_client()

    # Balance before: 0
    try:
        bal_before = algod_c.account_info(new_addr).get("amount", 0)
    except Exception:
        bal_before = 0
    assert bal_before == 0

    resp = client.post("/api/faucet", json={"address": new_addr})
    assert resp.status_code == 200, f"Faucet failed: {resp.text}"
    data = resp.json()
    assert data["ok"] is True
    assert data["algo_txid"] is not None

    # Balance after: 10 ALGO = 10,000,000 microAlgos
    info_after = algod_c.account_info(new_addr)
    bal_after = info_after.get("amount", 0)
    assert bal_after == 10_000_000, f"Expected 10,000,000 microAlgos, got {bal_after}"


def test_live_pass_purchase_pays_the_vendor_and_is_listed():
    """
    A pass is a plain payment to the vendor. client2 buys the service pass for sandbox_mcp-1:
    - quote -> client2 signs -> the test submits it to algod (the browser does exactly this)
    - client2 pays price + 1 fee, the VENDOR receives the price, the treasury is untouched
    - /api/passes/<client2> lists it with the vendor and the right expiry
    """
    import time as _time
    algod_c = chain.get_algod_client()
    accounts_data = config.load_accounts()
    c2 = accounts_data["accounts"]["client2"]
    c2_addr, c2_sk = c2["address"], mnemonic.to_private_key(c2["mnemonic"])
    m = config.load_marketplace()
    item = next(l for l in m["listings"] if l["id"] == "sandbox_mcp-1")
    vendor = m["vendors"][item["vendor"]]["address"]
    treasury = config.get_treasury_address()
    price = item["pass"]["price"]

    before = {a: algod_c.account_info(a).get("amount", 0) for a in (c2_addr, vendor, treasury)}

    quote = client.post("/api/passes/quote", json={"address": c2_addr, "scope": "listing:sandbox_mcp-1"})
    assert quote.status_code == 200, quote.text
    q = quote.json()
    assert q["vendor"]["address"] == vendor and q["price"] == price and q["asset"] == "ALGO"

    stxn = encoding.msgpack_decode(q["txn"]).sign(c2_sk)
    txid = algod_c.send_transaction(stxn)
    from algosdk import transaction as _tx
    _tx.wait_for_confirmation(algod_c, txid, 10)

    after = {a: algod_c.account_info(a).get("amount", 0) for a in (c2_addr, vendor, treasury)}
    print(f"\n[PASS PURCHASE] client2 {after[c2_addr]-before[c2_addr]}, vendor +{after[vendor]-before[vendor]}, treasury {after[treasury]-before[treasury]}")
    assert before[c2_addr] - after[c2_addr] == price + q["fee"]
    assert after[vendor] - before[vendor] == price
    assert after[treasury] == before[treasury]

    got = []
    for _ in range(20):
        got = client.get(f"/api/passes/{c2_addr}").json()
        if any(p["txid"] == txid for p in got):
            break
        _time.sleep(1)
    mine = next(p for p in got if p["txid"] == txid)
    assert mine["scope"] == "listing:sandbox_mcp-1" and mine["kind"] == "service"
    assert mine["vendor"]["id"] == item["vendor"] and mine["amount"] == price
    assert mine["expiresAt"] - mine["purchasedAt"] == 30 * 86400
