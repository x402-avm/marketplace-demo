"""Configuration loader for marketplace gateway backend."""

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
ALGO_ROOT = BASE_DIR.parents[1]

ACCOUNTS_FILE = ALGO_ROOT / "chain" / "accounts.json"
SERVERS_MARKETPLACE_FILE = ALGO_ROOT / "servers" / "marketplace.json"
FIXTURE_MARKETPLACE_FILE = BASE_DIR / "tests" / "fixtures" / "marketplace.json"

# In-memory sensitive accounts cache - NEVER returned via API, NEVER logged
_ACCOUNTS_DATA: Dict[str, Any] = {}
_MARKETPLACE_DATA: Dict[str, Any] = {}


def load_accounts() -> Dict[str, Any]:
    global _ACCOUNTS_DATA
    if _ACCOUNTS_DATA:
        return _ACCOUNTS_DATA
    if ACCOUNTS_FILE.exists():
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            _ACCOUNTS_DATA = json.load(f)
    return _ACCOUNTS_DATA


def load_marketplace() -> Dict[str, Any]:
    global _MARKETPLACE_DATA
    override_path = os.environ.get("MARKETPLACE_JSON")
    target_path = Path(override_path) if override_path else SERVERS_MARKETPLACE_FILE

    if target_path.exists():
        with open(target_path, "r", encoding="utf-8") as f:
            _MARKETPLACE_DATA = json.load(f)
    elif FIXTURE_MARKETPLACE_FILE.exists():
        with open(FIXTURE_MARKETPLACE_FILE, "r", encoding="utf-8") as f:
            _MARKETPLACE_DATA = json.load(f)
    else:
        _MARKETPLACE_DATA = {}
    return _MARKETPLACE_DATA


def reload_config():
    global _ACCOUNTS_DATA, _MARKETPLACE_DATA
    _ACCOUNTS_DATA = {}
    _MARKETPLACE_DATA = {}
    load_accounts()
    load_marketplace()


def get_network() -> str:
    m = load_marketplace()
    if "network" in m and m["network"]:
        return m["network"]
    a = load_accounts()
    if "network" in a and a["network"]:
        return a["network"]
    raise RuntimeError("network is not set in marketplace.json or accounts.json")


def get_genesis_hash() -> str:
    a = load_accounts()
    if "genesis_hash" in a and a["genesis_hash"]:
        return a["genesis_hash"]
    m = load_marketplace()
    if "genesis_hash" in m and m["genesis_hash"]:
        return m["genesis_hash"]
    net = m.get("network") or a.get("network")
    if net and ":" in net:
        return net.split(":", 1)[1]
    try:
        from app import chain
        algod_c = chain.get_algod_client()
        gh = algod_c.suggested_params().gh
        if gh:
            return gh
    except Exception as e:
        raise RuntimeError(f"genesis_hash missing from accounts.json and failed to query algod: {e}")
    raise RuntimeError("genesis_hash missing from accounts.json and algod returned empty hash")


def get_algod_url() -> str:
    a = load_accounts()
    return os.environ.get("ALGOD_URL", a.get("algod_url", "http://localhost:4001"))


def get_algod_token() -> str:
    a = load_accounts()
    return os.environ.get("ALGOD_TOKEN", a.get("algod_token", "a" * 64))


def get_kmd_url() -> str:
    a = load_accounts()
    return os.environ.get("KMD_URL", a.get("kmd_url", "http://localhost:4002"))


def get_indexer_url() -> str:
    a = load_accounts()
    return os.environ.get("INDEXER_URL", a.get("indexer_url", "http://localhost:8980"))


def get_assets() -> Dict[str, int]:
    m = load_marketplace()
    if "assets" in m:
        return m["assets"]
    a = load_accounts()
    return {
        "ALGO": 0,
        "mUSD": a.get("musd_asset_id", 1011),
        "AI-SUB": a.get("subscription_asset_id", 1010),
    }


def get_treasury_address() -> str:
    m = load_marketplace()
    if "treasury" in m:
        return m["treasury"]
    a = load_accounts()
    return a.get("accounts", {}).get("server", {}).get("address", "")


def get_passes_config() -> Dict[str, Any]:
    m = load_marketplace()
    return m.get("passes", {"days": 30, "note_prefix": "x402-pass:"})


def get_public_config() -> Dict[str, Any]:
    """Return public configuration safe for clients (NO private keys/mnemonics)."""
    return {
        "network": get_network(),
        "genesisHash": get_genesis_hash(),
        "algodUrl": get_algod_url(),
        "indexerUrl": get_indexer_url(),
        "kmdUrl": get_kmd_url(),
        "token": get_algod_token(),
        "assets": get_assets(),
        "treasury": get_treasury_address(),
        "passes": get_passes_config(),
    }


def get_server_mnemonic() -> str:
    """Internal use only - retrieves treasury signing mnemonic."""
    a = load_accounts()
    server_acc = a.get("accounts", {}).get("server", {})
    return server_acc.get("mnemonic", "")


def get_vendor_accounts() -> Dict[str, Any]:
    """Internal use only - retrieves vendor accounts if stored in accounts.json."""
    a = load_accounts()
    return {k: v for k, v in a.get("accounts", {}).items() if k.startswith("vendor")}
