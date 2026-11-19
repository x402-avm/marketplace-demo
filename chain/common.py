"""Common configuration and client helpers for Algorand LocalNet."""

from pathlib import Path
import json
from algosdk.kmd import KMDClient
from algosdk.v2client import algod, indexer

ALGOD_URL = "http://localhost:4001"
KMD_URL = "http://localhost:4002"
INDEXER_URL = "http://localhost:8980"
TOKEN = "a" * 64
ACCOUNTS_FILE = Path(__file__).parent / "accounts.json"


def algod_client() -> algod.AlgodClient:
    """Return an Algod client configured for LocalNet."""
    return algod.AlgodClient(TOKEN, ALGOD_URL)


def kmd_client() -> KMDClient:
    """Return a KMD client configured for LocalNet."""
    return KMDClient(TOKEN, KMD_URL)


def indexer_client() -> indexer.IndexerClient:
    """Return an Indexer client configured for LocalNet."""
    return indexer.IndexerClient("", INDEXER_URL)


def dispenser() -> tuple[str, str]:
    """
    Find and return (address, private_key) for the dispenser account.
    Selects the address with the largest balance from the KMD wallet
    'unencrypted-default-wallet' (password '').
    """
    kmd = kmd_client()
    algod_c = algod_client()

    wallets = kmd.list_wallets()
    target_wallet_id = None
    for w in wallets:
        if w.get("name") == "unencrypted-default-wallet":
            target_wallet_id = w.get("id")
            break

    if not target_wallet_id:
        raise RuntimeError("Wallet 'unencrypted-default-wallet' not found in KMD")

    handle = kmd.init_wallet_handle(target_wallet_id, "")
    try:
        addresses = kmd.list_keys(handle)
        if not addresses:
            raise RuntimeError("No addresses found in unencrypted-default-wallet")

        largest_addr = None
        largest_balance = -1
        for addr in addresses:
            info = algod_c.account_info(addr)
            balance = info.get("amount", 0)
            if balance > largest_balance:
                largest_balance = balance
                largest_addr = addr

        if not largest_addr:
            raise RuntimeError("Could not determine dispenser address with largest balance")

        private_key = kmd.export_key(handle, "", largest_addr)
        return largest_addr, private_key
    finally:
        kmd.release_wallet_handle(handle)


def load_accounts() -> dict:
    """Load and return accounts data from ACCOUNTS_FILE."""
    if not ACCOUNTS_FILE.exists():
        raise FileNotFoundError(f"Accounts file does not exist: {ACCOUNTS_FILE}")
    with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)
