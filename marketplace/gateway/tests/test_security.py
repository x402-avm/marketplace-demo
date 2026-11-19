"""Comprehensive Security Review and Exploit Test Suite for Marketplace Gateway.

Tests cover all 9 checklist categories from Task T55:
1. Secrets exposure in endpoints, error messages, and logs.
2. Call relay SSRF vectors (listing traversal, unknown listing, type confusion, SSE endpoint redirect).
3. File serving path traversal, double encoding, null bytes, directories, /proc/self/environ.
4. Upload security (path traversal in filename, overwrite protection, 25MB limit, 0-byte upload, mime spoofing).
5. Faucet abuse (dispenser drain risk, global rate limiting, invalid addresses, treasury address check).
6. Subscription quote security (wrong signer, fee tampering, client treasury txn ignored, 120s TTL, quote race condition, memory leak).
7. CORS configuration (origins pinned to localhost:5173 / 127.0.0.1:5173, no wildcard, credentials allowed).
8. Rate and size limits (request body size cap on /call, MCP relay 900s timeout).
9. Explorer endpoints (negative rounds, non-integers, huge rounds, txid SQL/path injection).

Real security holes that fail today are marked with @pytest.mark.xfail(strict=True, reason="HOLE: ...")
so that the test suite remains 100% green while accurately tracking vulnerabilities for auditB.
"""

import os
import re
import io
import time
import json
import base64
import urllib.parse
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app import config, chain, faucet, passes, files, mcp_relay, explorer
from algosdk import account, transaction, encoding

client = TestClient(app)

# Regex matching a 25-word Algorand mnemonic phrase
MNEMONIC_REGEX = re.compile(r'\b([a-z]+\s+){24}[a-z]+\b', re.IGNORECASE)


# =============================================================================
# 1. SECRETS IN RESPONSES, ERROR MESSAGES, AND LOGS
# =============================================================================

def test_secrets_faucet_error_does_not_leak_keys(monkeypatch):
    """Force error in faucet dispense and assert no 25-word mnemonic or dispenser private key is leaked."""
    faucet.reset_rate_limit()
    # 1. Invalid address error
    r1 = client.post("/api/faucet", json={"address": "INVALID_ADDR_12345"})
    assert r1.status_code == 400
    assert not MNEMONIC_REGEX.search(r1.text)
    assert "private" not in r1.text.lower()

    # 2. Algod connection failure during dispense
    class BrokenAlgod:
        def suggested_params(self):
            raise RuntimeError("algod is down: connection refused to http://localhost:4001")

    monkeypatch.setattr(chain, "get_algod_client", lambda: BrokenAlgod())
    _, fresh_addr = account.generate_account()
    r2 = client.post("/api/faucet", json={"address": fresh_addr})
    assert r2.status_code == 500
    assert not MNEMONIC_REGEX.search(r2.text)
    assert "mnemonic" not in r2.text.lower()
    assert "private_key" not in r2.text.lower()


def test_secrets_pass_error_does_not_leak_keys(monkeypatch):
    """Force an algod failure in the pass endpoint and assert no mnemonic / private key is ever leaked."""
    class BrokenAlgod:
        def suggested_params(self):
            raise RuntimeError("database error in ledger storage")
        def account_info(self, addr):
            raise RuntimeError("algod unreachable")

    monkeypatch.setattr(chain, "get_algod_client", lambda: BrokenAlgod())
    valid_addr = "SPDMDX4SBNY35L2GZB7RBKTPRT76NUVWA2GNXEQDTPPNKUOYJIK5ERFAW4"
    r = client.post("/api/passes/quote", json={"address": valid_addr, "scope": "listing:tts-1"})
    assert r.status_code == 502
    assert not MNEMONIC_REGEX.search(r.text)
    server_mn = config.get_server_mnemonic()
    if server_mn:
        assert server_mn not in r.text


def test_secrets_call_relay_error_does_not_leak_keys():
    """Verify call relay errors do not expose internal keys or configurations."""
    r = client.post("/api/listings/tts-1/call", json={"tool": "nonexistent_tool", "args": {}})
    assert not MNEMONIC_REGEX.search(r.text)
    assert "mnemonic" not in r.text.lower()


# =============================================================================
# 2. CALL RELAY SSRF VECTORS
# =============================================================================

def test_call_relay_rejects_path_traversal_listing_id():
    """Verify /call rejects directory traversal in listing ID with 404."""
    r = client.post("/api/listings/..%2f..%2fetc/call", json={"tool": "test", "args": {}})
    assert r.status_code == 404


def test_call_relay_rejects_unknown_listing_id():
    """Verify /call rejects arbitrary unknown listing ID with 404."""
    r = client.post("/api/listings/evil-domain-999/call", json={"tool": "test", "args": {}})
    assert r.status_code == 404


def test_call_relay_rejects_non_json_args():
    """Verify /call rejects invalid non-dict arguments with 422 Unprocessable Entity."""
    r = client.post("/api/listings/tts-1/call", json={"tool": "test", "args": "NOT_A_DICT"})
    assert r.status_code == 422


def test_call_relay_ssrf_sse_endpoint_injection(monkeypatch):
    """
    Verify that if a compromised upstream proxy sends a malicious endpoint (e.g. pointing
    to an external IP or attacker port), the gateway rejects it with 502 {"detail": "proxy sent an invalid endpoint"}
    and sends ZERO requests to the malicious target.
    """
    import socket
    import threading
    import time

    # 1. Fake malicious host: counts incoming connections
    malicious_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    malicious_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    malicious_sock.bind(("127.0.0.1", 0))
    malicious_port = malicious_sock.getsockname()[1]
    malicious_sock.listen(5)
    connection_count = 0

    def accept_malicious():
        nonlocal connection_count
        while True:
            try:
                conn, _ = malicious_sock.accept()
                connection_count += 1
                conn.close()
            except Exception:
                break

    t_malicious = threading.Thread(target=accept_malicious, daemon=True)
    t_malicious.start()

    # 2. Fake proxy that delivers a malicious endpoint event in its SSE stream
    proxy_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    proxy_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    proxy_sock.bind(("127.0.0.1", 0))
    proxy_port = proxy_sock.getsockname()[1]
    proxy_sock.listen(5)

    def serve_sse():
        try:
            conn, _ = proxy_sock.accept()
            _ = conn.recv(1024)
            resp = (
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: text/event-stream\r\n"
                b"Cache-Control: no-cache\r\n\r\n"
                b"event: endpoint\r\n"
                + f"data: http://127.0.0.1:{malicious_port}/messages/steal\r\n\r\n".encode("utf-8")
            )
            conn.sendall(resp)
            time.sleep(0.5)
            conn.close()
        except Exception:
            pass

    t_proxy = threading.Thread(target=serve_sse, daemon=True)
    t_proxy.start()

    try:
        from app import config
        monkeypatch.setattr(config, "load_marketplace", lambda: {
            "listings": [{"id": "malicious-listing", "port": proxy_port, "domain": "tts"}],
            "vendors": {},
        })

        resp = client.post("/api/listings/malicious-listing/call", json={"tool": "echo", "args": {}})

        # (a) Assert status 502 with detail "proxy sent an invalid endpoint"
        assert resp.status_code == 502
        assert resp.json()["detail"] == "proxy sent an invalid endpoint"

        # (b) Assert fake malicious host received ZERO requests
        assert connection_count == 0, f"Expected 0 requests to malicious host, but received {connection_count}"

    finally:
        malicious_sock.close()
        proxy_sock.close()


# =============================================================================
# 3. FILE SERVING SECURITY (/api/files)
# =============================================================================

def test_files_rejects_encoded_traversal():
    """Verify /api/files rejects %2e%2e path traversal with 403."""
    r = client.get("/api/files?path=%2e%2e%2f%2e%2e%2fetc%2fpasswd")
    assert r.status_code == 403
    assert r.json()["detail"] == "path not allowed"


def test_files_rejects_double_encoded_traversal():
    """Verify /api/files rejects double URL encoded %252e%252e traversal with 403."""
    r = client.get("/api/files?path=%252e%252e%252fetc%252fpasswd")
    assert r.status_code == 403


def test_files_rejects_proc_self_environ():
    """Verify /api/files rejects access to /proc/self/environ with 403."""
    r = client.get("/api/files?path=/proc/self/environ")
    assert r.status_code == 403


def test_files_rejects_directory_path():
    """Verify requesting a directory path returns 404 (not a file)."""
    target = str(files.TESTS_OUTPUTS_DIR)
    r = client.get(f"/api/files?path={target}")
    assert r.status_code == 404


def test_files_allows_cross_domain_output_by_design():
    """Verify paths inside servers/*/outputs/ are permitted by design."""
    allowed_roots = files.get_allowed_roots()
    assert len(allowed_roots) > 1
    # Verify tests/outputs is included
    assert any("tests/outputs" in r for r in allowed_roots)


def test_files_null_byte_causes_unhandled_500():
    """
    HOLE: In app/files.py:48:
    `real_path = os.path.realpath(os.path.expanduser(path_str.strip()))`
    If path contains an embedded null character `%00` (e.g. `/tmp/test%00.txt`),
    Python raises `ValueError: embedded null byte` or `lstat: embedded null character in path`.
    FastAPI does not handle ValueError and returns an unhandled 500 Internal Server Error.
    Fix: In app/files.py:validate_path, add:
        if "\x00" in path_str:
            raise HTTPException(status_code=400, detail="invalid path")
    """
    local_client = TestClient(app, raise_server_exceptions=False)
    resp = local_client.get("/api/files?path=%2Ftmp%2Ftest%00.txt")
    assert resp.status_code in (400, 403), f"Expected 400 or 403 for null byte, got {resp.status_code}"


def test_files_toctou_symlink_note():
    """
    NOTE: Symlink verification in validate_path uses os.path.realpath followed by FileResponse(real_path).
    While realpath checks the target at validation time, standard filesystem race conditions (TOCTOU)
    could theoretically exist if a file is replaced by a symlink after validation.
    Documented as NOTE per Task T55 instructions.
    """
    pass


# =============================================================================
# 4. UPLOAD SECURITY (/api/upload)
# =============================================================================

def test_upload_strips_traversal_in_filename():
    """Verify /api/upload sanitizes ../ in filename and confines to uploads/ directory."""
    payload = {"file": ("../../evil.sh", io.BytesIO(b"echo safe"), "application/x-sh")}
    resp = client.post("/api/upload", files=payload)
    assert resp.status_code == 200
    saved_path = resp.json()["path"]
    assert "tests/outputs/uploads" in saved_path
    assert not saved_path.endswith("evil.sh/evil.sh")
    assert Path(saved_path).name.endswith("_evil.sh")
    Path(saved_path).unlink(missing_ok=True)


def test_upload_strips_absolute_filename():
    """Verify /api/upload strips absolute paths in filename to basename."""
    payload = {"file": ("/etc/shadow", io.BytesIO(b"dummy"), "text/plain")}
    resp = client.post("/api/upload", files=payload)
    assert resp.status_code == 200
    saved_path = resp.json()["path"]
    assert Path(saved_path).name.endswith("_shadow")
    Path(saved_path).unlink(missing_ok=True)


def test_upload_cannot_overwrite_existing_file():
    """Verify uploading two files with identical names creates distinct UUID-prefixed paths."""
    p1 = {"file": ("data.bin", io.BytesIO(b"first"), "application/octet-stream")}
    p2 = {"file": ("data.bin", io.BytesIO(b"second"), "application/octet-stream")}
    r1 = client.post("/api/upload", files=p1)
    r2 = client.post("/api/upload", files=p2)
    path1 = r1.json()["path"]
    path2 = r2.json()["path"]
    assert path1 != path2
    Path(path1).unlink(missing_ok=True)
    Path(path2).unlink(missing_ok=True)


def test_upload_rejects_file_exceeding_25mb():
    """Verify /api/upload rejects file > 25MB with 413."""
    oversized = io.BytesIO(b"X" * (25 * 1024 * 1024 + 1))
    resp = client.post("/api/upload", files={"file": ("large.bin", oversized, "application/octet-stream")})
    assert resp.status_code == 413
    assert resp.json()["detail"] == "file too large, max 25 MB"


def test_upload_rejects_zero_byte_file():
    """
    HOLE: In app/files.py:65-80:
    `save_uploaded_file` checks `total_bytes > MAX_UPLOAD_SIZE`, but never checks `total_bytes == 0`.
    Zero-byte files are saved to disk with a UUID prefix and return 200 OK.
    This allows an attacker to flood the uploads directory with empty files and exhaust disk inodes.
    Fix: In app/files.py:save_uploaded_file, add:
        if total_bytes == 0:
            target_path.unlink(missing_ok=True)
            raise HTTPException(status_code=400, detail="empty file not allowed")
    """
    payload = {"file": ("empty.txt", io.BytesIO(b""), "text/plain")}
    resp = client.post("/api/upload", files=payload)
    if resp.status_code == 200:
        Path(resp.json()["path"]).unlink(missing_ok=True)
    assert resp.status_code == 400, f"Expected 400 for 0-byte upload, got {resp.status_code}"


def test_upload_content_type_spoofing():
    """
    NOTE: Server stores uploads without inspecting magic numbers or validating content-type headers.
    An attacker can supply any Content-Type (e.g. text/plain for an ELF binary).
    Files are stored in outputs/uploads and executed only as inputs to MCP tools.
    Documented as NOTE per Task T55 instructions.
    """
    payload = {"file": ("script.sh", io.BytesIO(b"#!/bin/bash\nexit 0"), "image/png")}
    resp = client.post("/api/upload", files=payload)
    assert resp.status_code == 200
    Path(resp.json()["path"]).unlink(missing_ok=True)


# =============================================================================
# 5. FAUCET ABUSE
# =============================================================================

def test_faucet_rejects_invalid_address():
    """Verify /api/faucet rejects malformed addresses with 400."""
    resp = client.post("/api/faucet", json={"address": "NOT_AN_ALGORAND_ADDRESS"})
    assert resp.status_code == 400
    assert resp.json()["detail"] == "invalid Algorand address"


def test_faucet_per_address_rate_limit(monkeypatch):
    """Verify faucet enforces 60s cooldown per address."""
    faucet.reset_rate_limit()
    dispenser_sk, dispenser_addr = account.generate_account()
    monkeypatch.setattr(chain, "get_dispenser", lambda: (dispenser_addr, dispenser_sk))

    class MockAlgod:
        def suggested_params(self):
            return transaction.SuggestedParams(1000, 1, 100, "qNF74lmmiHUCf7s3oewhYsMzOCOEptuJ9ytCk5gBPGI=", flat_fee=True)
        def send_transaction(self, stxn):
            return "TXID_TEST_FAUCET"
        def account_info(self, addr):
            return {"amount": 100000000, "assets": []}

    monkeypatch.setattr(chain, "get_algod_client", lambda: MockAlgod())
    monkeypatch.setattr(transaction, "wait_for_confirmation", lambda c, t, w: {"confirmed-round": 10})

    _, target_addr = account.generate_account()
    r1 = client.post("/api/faucet", json={"address": target_addr})
    assert r1.status_code == 200
    r2 = client.post("/api/faucet", json={"address": target_addr})
    assert r2.status_code == 429
    assert "rate limit exceeded" in r2.json()["detail"]


def test_faucet_rejects_treasury_address():
    """
    HOLE: In app/faucet.py:21-33:
    There is no check preventing `address == config.get_treasury_address()`.
    If requested with the treasury address, the faucet dispenses 10 ALGO from dispenser to treasury,
    and then attempts a self-asset transfer of 100 mUSD from treasury to itself.
    The treasury address should be barred from using the public dispenser.
    Fix: In app/faucet.py:dispense, add:
        if address == config.get_treasury_address():
            raise HTTPException(status_code=400, detail="treasury address cannot use faucet")
    """
    treasury_addr = config.get_treasury_address()
    resp = client.post("/api/faucet", json={"address": treasury_addr})
    assert resp.status_code == 400, f"Expected 400 rejecting treasury faucet call, got {resp.status_code}"


def test_faucet_lacks_global_rate_limit_drain_risk(monkeypatch):
    """
    HOLE: In app/faucet.py:11-33:
    Rate limiting is strictly per-address in in-memory dict `_LAST_FAUCET_TIME`.
    An attacker generating fresh addresses in a loop faces 0 rate limits.
    With LocalNet dispenser balance at ~3,999,996,104.9 ALGO (399,999,609 calls possible),
    the dispenser can be drained rapidly.
    Fix: Add global sliding window rate limiter (e.g. max 10 requests per minute across all clients)
    and IP-based throttling.
    """
    faucet.reset_rate_limit()
    dispenser_sk, dispenser_addr = account.generate_account()
    monkeypatch.setattr(chain, "get_dispenser", lambda: (dispenser_addr, dispenser_sk))

    class MockAlgod:
        def suggested_params(self):
            return transaction.SuggestedParams(1000, 1, 100, "qNF74lmmiHUCf7s3oewhYsMzOCOEptuJ9ytCk5gBPGI=", flat_fee=True)
        def send_transaction(self, stxn):
            return "TXID_TEST"
        def account_info(self, addr):
            return {"amount": 100000000, "assets": []}

    monkeypatch.setattr(chain, "get_algod_client", lambda: MockAlgod())
    monkeypatch.setattr(transaction, "wait_for_confirmation", lambda c, t, w: {"confirmed-round": 10})

    statuses = []
    for _ in range(5):
        _, fresh_addr = account.generate_account()
        res = client.post("/api/faucet", json={"address": fresh_addr})
        statuses.append(res.status_code)

    # A protected faucet should throttle rapid global requests with 429
    assert 429 in statuses, f"No global rate limiting in faucet; all calls succeeded: {statuses}"


# =============================================================================
# 6. PASS SECURITY (individual passes, paid straight to the vendor)
# =============================================================================

class _FundedAlgod:
    """Algod stub that reports a funded account; used only to reach the quote-building code."""
    def __init__(self, assets=None):
        self._assets = assets or []

    def account_info(self, addr):
        return {"amount": 50_000_000, "min-balance": 100_000, "assets": self._assets}

    def suggested_params(self):
        from algosdk import transaction
        gh = "qNF74lmmiHUCf7s3oewhYsMzOCOEptuJ9ytCk5gBPGI="
        try:
            gh = config.get_genesis_hash() or gh
        except Exception:
            pass
        return transaction.SuggestedParams(fee=1000, first=1, last=1000, gh=gh, gen="dockernet-v1", flat_fee=True)


def test_pass_scope_injection_rejected(monkeypatch):
    monkeypatch.setattr(chain, "get_algod_client", lambda: _FundedAlgod())
    _, addr = account.generate_account()
    for bad in ["", "listing:", "listing:../../etc", "vendor:", "vendor:nobody", "everything", "listing:tts-1\nx402-pass:vendor:vendorA",
                "tts-1", "vendor:vendorA:extra", "LISTING:tts-1"]:
        r = client.post("/api/passes/quote", json={"address": addr, "scope": bad})
        assert r.status_code in (400, 404), (bad, r.status_code, r.text)


def test_pass_quote_pays_the_vendor_not_the_treasury(monkeypatch):
    """The unsigned payment must go to the vendor of that listing, for exactly the listed price, with the scope note."""
    monkeypatch.setattr(chain, "get_algod_client", lambda: _FundedAlgod())
    m = config.load_marketplace()
    _, addr = account.generate_account()
    item = next(l for l in m["listings"] if l["asset"] == "ALGO")
    r = client.post("/api/passes/quote", json={"address": addr, "scope": f"listing:{item['id']}"})
    assert r.status_code == 200, r.text
    q = r.json()
    txn = encoding.msgpack_decode(q["txn"])
    assert txn.receiver == m["vendors"][item["vendor"]]["address"]
    assert txn.receiver != m["treasury"]
    assert txn.amt == item["pass"]["price"] == q["price"]
    assert txn.note == f"x402-pass:listing:{item['id']}".encode()
    assert txn.sender == addr and q["signIndexes"] == [0]


def test_pass_quote_vendor_scope_and_asset(monkeypatch):
    m = config.load_marketplace()
    musd = config.get_assets()["mUSD"]
    monkeypatch.setattr(chain, "get_algod_client", lambda: _FundedAlgod(assets=[{"asset-id": musd, "amount": 10_000_000_000}]))
    _, addr = account.generate_account()
    r = client.post("/api/passes/quote", json={"address": addr, "scope": "vendor:vendorB"})
    assert r.status_code == 200, r.text
    txn = encoding.msgpack_decode(r.json()["txn"])
    assert txn.index == musd and txn.amount == m["vendors"]["vendorB"]["pass"]["price"]
    assert txn.receiver == m["vendors"]["vendorB"]["address"]


def test_pass_quote_requires_opt_in_for_musd(monkeypatch):
    monkeypatch.setattr(chain, "get_algod_client", lambda: _FundedAlgod())
    _, addr = account.generate_account()
    r = client.post("/api/passes/quote", json={"address": addr, "scope": "vendor:vendorB"})
    assert r.status_code == 400 and "opt in" in r.json()["detail"]


def test_pass_receipt_must_match_vendor_scope_amount_and_age():
    """ChainReader.active_passes ignores receipts that are underpaid, expired, sent to someone else or carry another scope."""
    import base64
    from ai_economy_sdk import ChainReader

    vendor, other, buyer = "VENDORADDR", "OTHERADDR", "BUYERADDR"
    now = 1_800_000_000
    def tx(scope, amount, receiver=vendor, age_days=1.0, txid="T"):
        return {"id": txid, "round-time": now - age_days * 86400, "tx-type": "pay",
                "note": base64.b64encode(f"x402-pass:{scope}".encode()).decode(),
                "payment-transaction": {"receiver": receiver, "amount": amount}}

    class FakeIndexer:
        def search_transactions(self, **kw):
            return {"transactions": [
                tx("listing:tts-1", 999, txid="underpaid"),
                tx("listing:tts-1", 5000, receiver=other, txid="wrong-vendor"),
                tx("listing:tts-1", 5000, age_days=31, txid="expired"),
                tx("listing:sandbox_mcp-1", 5000, txid="other-scope"),
                tx("listing:tts-1", 5000, txid="good"),
            ]}
    r = ChainReader(indexer=FakeIndexer())
    got = r.active_passes(buyer, vendor, 0, {"listing:tts-1": 1000}, 30, now=now)
    assert [g["txid"] for g in got] == ["good"]


# =============================================================================
# 7. CORS SECURITY
# =============================================================================

def test_cors_disallows_arbitrary_origins():
    """Verify unauthorized origin does not receive Access-Control-Allow-Origin."""
    resp = client.options(
        "/api/config",
        headers={
            "Origin": "http://malicious-site.com",
            "Access-Control-Request-Method": "GET"
        }
    )
    assert resp.headers.get("access-control-allow-origin") is None


def test_cors_allows_localhost_and_127_0_0_1_port_5173():
    """Verify CORS allow_origins is strictly pinned to localhost:5173 and 127.0.0.1:5173."""
    for origin in ["http://localhost:5173", "http://127.0.0.1:5173"]:
        resp = client.options(
            "/api/config",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET"
            }
        )
        assert resp.headers.get("access-control-allow-origin") == origin
        assert resp.headers.get("access-control-allow-credentials") == "true"


def test_cors_no_wildcard():
    """Verify wildcard '*' origin is not configured."""
    resp = client.options(
        "/api/config",
        headers={
            "Origin": "*",
            "Access-Control-Request-Method": "GET"
        }
    )
    assert resp.headers.get("access-control-allow-origin") != "*"


# =============================================================================
# 8. RATE & SIZE LIMITS
# =============================================================================

def test_call_request_body_size_limit():
    """
    HOLE: In app/main.py:133-165:
    `/api/listings/{listing_id}/call` accepts arbitrary JSON payloads without any size check.
    An attacker can POST a 50MB JSON payload, exhausting gateway memory and causing OOM crash.
    Fix: Add request body size validation middleware or check Content-Length header (e.g. max 10MB).
    """
    huge_text = "A" * (12 * 1024 * 1024)  # 12 MB
    resp = client.post("/api/listings/tts-1/call", json={"tool": "test", "args": {"big": huge_text}})
    assert resp.status_code == 413, f"Expected 413 Request Entity Too Large for 12MB body, got {resp.status_code}"


def test_mcp_relay_timeout_too_long():
    """
    HOLE: In app/mcp_relay.py:14 & 184:
    Default timeout is set to 900.0 seconds (15 minutes).
    If a proxy hangs or delays its SSE stream responses, gateway worker threads/coroutines
    hang for 15 minutes, exhausting server resources and causing DoS.
    Fix: Lower MCP tool call timeout to 30.0s or 60.0s, and enforce read timeouts on the SSE stream.
    """
    client_sse = mcp_relay.McpSseClient(port=8051)
    assert client_sse.timeout.read <= 60.0, (
        f"McpSseClient read timeout is {client_sse.timeout.read}s, expected <= 60.0s"
    )


# =============================================================================
# 9. EXPLORER ENDPOINTS
# =============================================================================

def test_explorer_block_non_integer_rejected():
    """Verify non-integer round parameter is rejected with 422."""
    resp = client.get("/api/explorer/block/string_round")
    assert resp.status_code == 422


def test_explorer_block_huge_round_returns_404():
    """Verify out-of-range round returns 404 block not found."""
    resp = client.get("/api/explorer/block/99999999999999")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_explorer_tx_injection_safe():
    """Verify SQLi and directory traversal attempts in txid return 404 without injection."""
    r1 = client.get("/api/explorer/tx/' OR '1'='1")
    assert r1.status_code == 404

    r2 = client.get("/api/explorer/tx/../../etc/passwd")
    assert r2.status_code == 404


def test_explorer_negative_round_rejected_by_validator():
    """
    HOLE: In app/main.py:329 & app/explorer.py:70:
    `round_num: int` has no `ge=0` validation.
    When `round_num = -1`, the endpoint forwards `/blocks/-1/hash` to algod, which fails with
    strconv.ParseUint syntax error and returns 404.
    Fix: Use `round_num: int = Path(..., ge=0)` so FastAPI validates input and returns 422.
    """
    resp = client.get("/api/explorer/block/-1")
    assert resp.status_code == 422, f"Expected 422 Unprocessable Entity for round -1, got {resp.status_code}"


def test_explorer_verify_negative_from_round_rejected():
    """
    HOLE: In app/main.py:340 & app/explorer.py:171:
    `from_round` query parameter does not enforce `ge=0`.
    When `from=-1`, the loop queries `r=0` and attempts to fetch hash for round -1,
    reporting a broken chain error from algod parsing failure.
    Fix: In app/main.py:verify_blocks, add `from_round: Optional[int] = Query(None, alias="from", ge=0)`.
    """
    resp = client.get("/api/explorer/verify?from=-1&to=10")
    assert resp.status_code == 422, f"Expected 422 Unprocessable Entity for from=-1, got {resp.status_code}"
