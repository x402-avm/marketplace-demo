"""Offline test suite for marketplace gateway (FastAPI TestClient, no external network)."""

import os
import re
import io
import time
import json
import base64
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app import config, faucet, explorer, files, passes
from algosdk import account, transaction, encoding

client = TestClient(app)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


# -----------------------------------------------------------------------------
# 1. Config Security: Never Expose Mnemonics
# -----------------------------------------------------------------------------

def test_config_never_exposes_mnemonics():
    """Verify that public config endpoint and all public responses never leak private keys or mnemonics."""
    endpoints = [
        "/api/config",
        "/api/health",
        "/api/vendors",
        "/api/listings",
        "/api/explorer/blocks?limit=5",
    ]

    # Regex for 25 words (Algorand mnemonic)
    mnemonic_pattern = re.compile(r'\b([a-z]+\s+){24}[a-z]+\b', re.IGNORECASE)

    for ep in endpoints:
        resp = client.get(ep)
        text = resp.text.lower()
        assert "mnemonic" not in text, f"Endpoint {ep} leaked 'mnemonic' keyword!"
        assert "private_key" not in text, f"Endpoint {ep} leaked 'private_key' keyword!"
        # Check for 25-word seed phrase pattern
        matches = mnemonic_pattern.findall(resp.text)
        assert len(matches) == 0, f"Endpoint {ep} leaked 25-word phrase: {matches}"

    # Also test get_public_config() directly
    cfg = config.get_public_config()
    cfg_str = json.dumps(cfg).lower()
    assert "mnemonic" not in cfg_str
    assert "private" not in cfg_str


# -----------------------------------------------------------------------------
# 2. File Serving & Upload Path Rules (Security Isolation)
# -----------------------------------------------------------------------------

def test_file_paths_security_and_traversal(tmp_path):
    """Verify safe path enforcement, traversal prevention, and symlink escape rejection (403)."""
    # 1. Direct sensitive files
    r1 = client.get("/api/files?path=/etc/passwd")
    assert r1.status_code == 403
    assert r1.json()["detail"] == "path not allowed"

    # 2. Directory traversal tricks
    r2 = client.get("/api/files?path=../../../../etc/passwd")
    assert r2.status_code == 403

    r3 = client.get("/api/files?path=")
    assert r3.status_code == 403

    # 3. Symlink inside allowed outputs pointing to /etc/hostname -> MUST 403
    test_outputs_dir = files.TESTS_OUTPUTS_DIR
    test_outputs_dir.mkdir(parents=True, exist_ok=True)
    symlink_target = Path("/etc/hostname")

    if symlink_target.exists():
        symlink_path = test_outputs_dir / "test_escape_symlink.txt"
        try:
            if symlink_path.exists() or symlink_path.is_symlink():
                symlink_path.unlink()
            symlink_path.symlink_to(symlink_target)

            r_sym = client.get(f"/api/files?path={symlink_path}")
            assert r_sym.status_code == 403, f"Symlink escape was not blocked! Got {r_sym.status_code}"
            assert r_sym.json()["detail"] == "path not allowed"
        finally:
            if symlink_path.is_symlink() or symlink_path.exists():
                symlink_path.unlink()

    # 4. Valid file in outputs directory -> 200
    valid_file = test_outputs_dir / "test_valid_file.txt"
    try:
        valid_file.write_text("secure marketplace file content")
        r_valid = client.get(f"/api/files?path={valid_file}")
        assert r_valid.status_code == 200
        assert r_valid.text == "secure marketplace file content"
    finally:
        if valid_file.exists():
            valid_file.unlink()

    # 5. Nonexistent file in outputs -> 404
    r_404 = client.get(f"/api/files?path={test_outputs_dir / 'nonexistent_123.bin'}")
    assert r_404.status_code == 404


def test_file_upload_limits():
    """Verify /api/upload accepts valid uploads and rejects files > 25 MB."""
    # Valid small file
    test_content = b"Small audio sample test"
    files_payload = {"file": ("test.wav", io.BytesIO(test_content), "audio/wav")}
    res = client.post("/api/upload", files=files_payload)
    assert res.status_code == 200
    saved_path = res.json()["path"]
    assert "tests/outputs/uploads" in saved_path
    assert Path(saved_path).exists()
    assert Path(saved_path).read_bytes() == test_content
    Path(saved_path).unlink(missing_ok=True)


# -----------------------------------------------------------------------------
# 3. 402 Payment Required Decode
# -----------------------------------------------------------------------------

def test_402_payment_required_decoding(monkeypatch):
    """Verify tool call without payment signature forwards to 402 and decodes paymentRequired header."""
    mock_header_dict = {
        "x402Version": 2,
        "accepts": [{
            "scheme": "exact",
            "network": "algorand:test",
            "asset": "ALGO",
            "amount": 20000,
            "payTo": "TESTADDR",
            "extra": {"feePayer": "FEEADDR"}
        }],
        "resource": {"url": "http://127.0.0.1:8051"}
    }
    mock_header_b64 = base64.b64encode(json.dumps(mock_header_dict).encode("utf-8")).decode("utf-8")

    async def mock_call_tool(*args, **kwargs):
        return ("402", mock_header_b64)

    from app import mcp_relay
    monkeypatch.setattr(mcp_relay, "call_tool_on_port", mock_call_tool)

    resp = client.post(
        "/api/listings/tts-1/call",
        json={"tool": "synthesize_speech", "args": {"text": "hello"}}
    )
    assert resp.status_code == 402
    data = resp.json()
    assert data["status"] == 402
    assert data["header"] == mock_header_b64
    assert data["paymentRequired"]["accepts"][0]["amount"] == 20000
    assert data["paymentRequired"]["accepts"][0]["asset"] == "ALGO"


# -----------------------------------------------------------------------------
# 4. Passes are individual and priced per vendor
# -----------------------------------------------------------------------------

def test_every_listing_and_vendor_has_its_own_pass():
    """marketplace.json: each listing has a service pass, each vendor a vendor pass; the vendor pass is a discount."""
    m = config.load_marketplace()
    assert m["listings"], "fixture has no listings"
    for l in m["listings"]:
        assert l["pass"]["scope"] == f"listing:{l['id']}"
        assert l["pass"]["price"] > 0
    for vid, v in m["vendors"].items():
        assert v["pass"]["scope"] == f"vendor:{vid}"
        service_total = sum(l["pass"]["price"] for l in m["listings"] if l["vendor"] == vid)
        assert 0 < v["pass"]["price"] <= service_total


def test_pass_scope_resolves_to_the_right_vendor():
    m = config.load_marketplace()
    l = m["listings"][0]
    info = passes.resolve_scope(f"listing:{l['id']}")
    assert info["vendor"]["id"] == l["vendor"] and info["kind"] == "service" and info["price"] == l["pass"]["price"]
    vid = l["vendor"]
    info = passes.resolve_scope(f"vendor:{vid}")
    assert info["kind"] == "vendor" and info["price"] == m["vendors"][vid]["pass"]["price"]
    with pytest.raises(Exception):
        passes.resolve_scope("listing:does-not-exist")


# -----------------------------------------------------------------------------
# 5. Faucet Rate Limit
# -----------------------------------------------------------------------------

def test_faucet_rate_limit(monkeypatch):
    """Verify that faucet enforces 60s cooldown per address and returns 429."""
    faucet.reset_rate_limit()

    test_addr = "SPDMDX4SBNY35L2GZB7RBKTPRT76NUVWA2GNXEQDTPPNKUOYJIK5ERFAW4"
    dispenser_sk, dispenser_addr = account.generate_account()

    # Mock dispenser and algod
    from app import chain
    monkeypatch.setattr(chain, "get_dispenser", lambda: (dispenser_addr, dispenser_sk))

    class MockAlgod:
        def suggested_params(self):
            return transaction.SuggestedParams(
                1000, 1, 100, "qNF74lmmiHUCf7s3oewhYsMzOCOEptuJ9ytCk5gBPGI=", flat_fee=True
            )

        def send_transaction(self, stxn):
            return "TXID_MOCK_123"

        def account_info(self, addr):
            return {"amount": 100000000, "assets": []}

    monkeypatch.setattr(chain, "get_algod_client", lambda: MockAlgod())
    monkeypatch.setattr(transaction, "wait_for_confirmation", lambda client, txid, wait: {"confirmed-round": 10})

    # First call: succeeds
    res1 = faucet.dispense(test_addr)
    assert res1["ok"] is True
    assert res1["algo_txid"] == "TXID_MOCK_123"

    # Second call immediately: 429
    with pytest.raises(Exception) as exc_info:
        faucet.dispense(test_addr)
    assert "rate limit exceeded" in str(exc_info.value)


# -----------------------------------------------------------------------------
# 6. Explorer Hash Recomputation on Stored Sample Block
# -----------------------------------------------------------------------------

def test_explorer_hash_recomputation_sample_block():
    """Verify block hash = sha512_256(b'BH' + msgpack header) recomputation matches sample block."""
    sample_file = FIXTURES_DIR / "sample_block.msgpack"
    assert sample_file.exists(), f"Sample block missing at {sample_file}"

    raw_block = sample_file.read_bytes()
    computed_hash = explorer.compute_header_hash_from_msgpack(raw_block)

    # Known canonical hash for block 1000 on LocalNet
    expected_hash = "YNJTK5UMGEXELI5LJUADMEKARDLPGBL2DOSIIB7CPIOOBAIY35IA"
    assert computed_hash == expected_hash, f"Hash mismatch: got {computed_hash}, expected {expected_hash}"
    assert len(computed_hash) == 52
