"""Algorand blockchain interaction utilities and clients."""

from typing import Tuple, Dict, Any, Optional
from algosdk.v2client import algod, indexer
from algosdk.kmd import KMDClient
from algosdk import mnemonic

from app import config


def get_algod_client() -> algod.AlgodClient:
    return algod.AlgodClient(config.get_algod_token(), config.get_algod_url())


def get_indexer_client() -> indexer.IndexerClient:
    return indexer.IndexerClient("", config.get_indexer_url())


def get_kmd_client() -> KMDClient:
    return KMDClient(config.get_algod_token(), config.get_kmd_url())


def get_dispenser() -> Tuple[str, str]:
    """
    Find and return (address, private_key) for the LocalNet dispenser.
    Selects the address with the largest balance from the KMD wallet
    'unencrypted-default-wallet' (password '').
    """
    kmd = get_kmd_client()
    algod_c = get_algod_client()

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
            bal = info.get("amount", 0)
            if bal > largest_balance:
                largest_balance = bal
                largest_addr = addr

        if not largest_addr:
            raise RuntimeError("Could not determine dispenser address with largest balance")

        private_key = kmd.export_key(handle, "", largest_addr)
        return largest_addr, private_key
    finally:
        kmd.release_wallet_handle(handle)


def get_server_key() -> str:
    """Retrieve private key for treasury/server account."""
    mn = config.get_server_mnemonic()
    if not mn:
        raise RuntimeError("Server mnemonic not found in accounts configuration")
    return mnemonic.to_private_key(mn)


def get_server_address() -> str:
    return config.get_treasury_address()
