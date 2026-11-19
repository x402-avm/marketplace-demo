"""Faucet endpoint: dispense 10 ALGO + 100 mUSD (if opted in) with 60s rate limit."""

import time
from typing import Dict, Any, Optional
from fastapi import HTTPException
from algosdk import transaction
from algosdk.encoding import is_valid_address

from app import chain, config

_LAST_FAUCET_TIME: Dict[str, float] = {}
RATE_LIMIT_SECONDS = 60.0
_GLOBAL_GRANTS: list[float] = []
GLOBAL_LIMIT = 30
GLOBAL_WINDOW_SECONDS = 600.0  # 10 minutes


def reset_rate_limit():
    """Testing helper to clear rate limit dictionary and global history."""
    global _LAST_FAUCET_TIME, _GLOBAL_GRANTS
    _LAST_FAUCET_TIME = {}
    _GLOBAL_GRANTS = []


def is_blocked_address(address: str) -> bool:
    """Check if address is treasury, vendor, or dispenser (all barred from faucet)."""
    try:
        treasury = config.get_treasury_address()
        if address == treasury:
            return True
    except Exception:
        pass

    try:
        accounts_data = config.load_accounts().get("accounts", {})
        for name in ("server", "vendorA", "vendorB", "vendorC", "vendorD"):
            if name in accounts_data and accounts_data[name].get("address") == address:
                return True
    except Exception:
        pass

    try:
        dispenser_addr, _ = chain.get_dispenser()
        if address == dispenser_addr:
            return True
    except Exception:
        pass

    return False


def dispense(address: str) -> Dict[str, Any]:
    if not address or not is_valid_address(address):
        raise HTTPException(status_code=400, detail="invalid Algorand address")

    try:
        dispenser_addr, _ = chain.get_dispenser()
        if address == dispenser_addr:
            raise HTTPException(
                status_code=400,
                detail="treasury, vendor, and dispenser addresses cannot use faucet"
            )
    except HTTPException:
        raise
    except Exception:
        pass

    now = time.time()

    # 1. Check global rate limit (max 30 grants per 10 minutes; burst limit of 4 per second)
    global _GLOBAL_GRANTS
    _GLOBAL_GRANTS = [t for t in _GLOBAL_GRANTS if (now - t) < GLOBAL_WINDOW_SECONDS]
    if len(_GLOBAL_GRANTS) >= GLOBAL_LIMIT:
        raise HTTPException(status_code=429, detail="faucet busy, try later")

    recent_1s = [t for t in _GLOBAL_GRANTS if (now - t) < 1.0]
    if len(recent_1s) >= 4:
        raise HTTPException(status_code=429, detail="faucet busy, try later")

    # 2. Check per-address rate limit (60s)
    last_time = _LAST_FAUCET_TIME.get(address, 0.0)
    if (now - last_time) < RATE_LIMIT_SECONDS:
        remaining = int(RATE_LIMIT_SECONDS - (now - last_time))
        raise HTTPException(
            status_code=429,
            detail=f"rate limit exceeded: max once per 60s (wait {remaining}s)"
        )

    algod_c = chain.get_algod_client()

    # 1. Dispense 10 ALGO from LocalNet dispenser
    try:
        dispenser_addr, dispenser_sk = chain.get_dispenser()
        sp = algod_c.suggested_params()
        algo_txn = transaction.PaymentTxn(dispenser_addr, sp, address, 10_000_000)
        stxn = algo_txn.sign(dispenser_sk)
        algo_txid = algod_c.send_transaction(stxn)
        transaction.wait_for_confirmation(algod_c, algo_txid, 4)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"dispenser ALGO transfer failed: {e}")

    # 2. Check mUSD opt-in and send 100 mUSD if opted in
    musd_txid = None
    musd_asset_id = config.get_assets().get("mUSD")
    if musd_asset_id and musd_asset_id > 0:
        try:
            info = algod_c.account_info(address)
            holding = [a for a in info.get("assets", []) if a.get("asset-id") == musd_asset_id]
            if holding:
                # User opted in to mUSD, send 100 mUSD (100 * 10^6 base units)
                server_addr = chain.get_server_address()
                server_sk = chain.get_server_key()
                sp2 = algod_c.suggested_params()
                axfer_txn = transaction.AssetTransferTxn(
                    server_addr,
                    sp2,
                    address,
                    100_000_000,
                    index=musd_asset_id
                )
                satxn = axfer_txn.sign(server_sk)
                musd_txid = algod_c.send_transaction(satxn)
                transaction.wait_for_confirmation(algod_c, musd_txid, 4)
        except Exception:
            # mUSD transfer failure shouldn't fail ALGO dispense
            pass

    _LAST_FAUCET_TIME[address] = now
    _GLOBAL_GRANTS.append(now)
    return {
        "ok": True,
        "address": address,
        "algo_txid": algo_txid,
        "musd_txid": musd_txid
    }
