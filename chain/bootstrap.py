#!/usr/bin/env python3
"""Idempotent bootstrapper for LocalNet accounts, vendors, subscription asset, and mUSD."""

import os
import json
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", category=DeprecationWarning)
from algosdk import account, mnemonic, transaction
import common
from x402_algorand.utils import caip2_from_genesis_hash

ROLES = ["server", "client1", "client2", "vendorA", "vendorB", "vendorC", "vendorD"]
CLIENT_TOPUP_TARGET = 1_000_000_000      # 1000 ALGO in microAlgos
CLIENT_TOPUP_THRESHOLD = 500_000_000     # 500 ALGO in microAlgos
VENDOR_TOPUP_TARGET = 100_000_000        # 100 ALGO in microAlgos
VENDOR_TOPUP_THRESHOLD = 50_000_000      # 50 ALGO in microAlgos


def main():
    algod = common.algod_client()
    sp = algod.suggested_params()
    gh = sp.gh
    network = caip2_from_genesis_hash(gh)

    accounts = {}
    subscription_asset_id = None
    musd_asset_id = None

    # Check if accounts.json already exists for this network
    if common.ACCOUNTS_FILE.exists():
        try:
            with open(common.ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
            if existing_data.get("genesis_hash") == gh or existing_data.get("network") == "algorand:" + gh:
                existing_accounts = existing_data.get("accounts", {})
                for r in ROLES:
                    if r in existing_accounts:
                        accounts[r] = existing_accounts[r]

                # Check existing subscription asset
                candidate_sub_id = existing_data.get("subscription_asset_id")
                if candidate_sub_id is not None:
                    try:
                        algod.asset_info(candidate_sub_id)
                        subscription_asset_id = int(candidate_sub_id)
                    except Exception:
                        subscription_asset_id = None

                # Check existing mUSD asset
                candidate_musd_id = existing_data.get("musd_asset_id")
                if candidate_musd_id is not None:
                    try:
                        algod.asset_info(candidate_musd_id)
                        musd_asset_id = int(candidate_musd_id)
                    except Exception:
                        musd_asset_id = None
        except Exception:
            pass

    # For any role not already present, generate a new random account
    for role in ROLES:
        if role not in accounts:
            sk, addr = account.generate_account()
            mn = mnemonic.from_private_key(sk)
            accounts[role] = {"address": addr, "mnemonic": mn}

    # Fund accounts from LocalNet dispenser if below threshold
    disp_addr, disp_sk = None, None
    for role in ROLES:
        addr = accounts[role]["address"]
        try:
            info = algod.account_info(addr)
            bal = info.get("amount", 0)
        except Exception:
            bal = 0

        is_vendor = role.startswith("vendor")
        threshold = VENDOR_TOPUP_THRESHOLD if is_vendor else CLIENT_TOPUP_THRESHOLD
        target = VENDOR_TOPUP_TARGET if is_vendor else CLIENT_TOPUP_TARGET

        if bal < threshold:
            needed = target - bal
            if needed > 0:
                if disp_addr is None:
                    disp_addr, disp_sk = common.dispenser()
                curr_sp = algod.suggested_params()
                ptxn = transaction.PaymentTxn(disp_addr, curr_sp, addr, needed)
                stxn = ptxn.sign(disp_sk)
                txid = algod.send_transaction(stxn)
                transaction.wait_for_confirmation(algod, txid, 4)

    # Subscription asset creation or reuse
    if subscription_asset_id is None:
        server_addr = accounts["server"]["address"]
        server_sk = mnemonic.to_private_key(accounts["server"]["mnemonic"])
        curr_sp = algod.suggested_params()
        actxn = transaction.AssetCreateTxn(
            sender=server_addr,
            sp=curr_sp,
            total=1_000_000,
            decimals=0,
            default_frozen=False,
            unit_name="PASS",
            asset_name="AI-SUB",
            manager=server_addr,
            reserve=server_addr,
        )
        stxn = actxn.sign(server_sk)
        txid = algod.send_transaction(stxn)
        res = transaction.wait_for_confirmation(algod, txid, 4)
        subscription_asset_id = int(res["asset-index"])

    # mUSD asset creation or reuse
    if musd_asset_id is None:
        server_addr = accounts["server"]["address"]
        server_sk = mnemonic.to_private_key(accounts["server"]["mnemonic"])
        curr_sp = algod.suggested_params()
        actxn = transaction.AssetCreateTxn(
            sender=server_addr,
            sp=curr_sp,
            total=10**15,
            decimals=6,
            default_frozen=False,
            unit_name="mUSD",
            asset_name="Marketplace USD",
            manager=server_addr,
            reserve=server_addr,
            freeze=None,
            clawback=None,
        )
        stxn = actxn.sign(server_sk)
        txid = algod.send_transaction(stxn)
        res = transaction.wait_for_confirmation(algod, txid, 4)
        musd_asset_id = int(res["asset-index"])

    # Opt into AI-SUB: vendorA..D, client1, client2
    for role in ["client1", "client2", "vendorA", "vendorB", "vendorC", "vendorD"]:
        addr = accounts[role]["address"]
        sk = mnemonic.to_private_key(accounts[role]["mnemonic"])
        info = algod.account_info(addr)
        opted_in = any(a.get("asset-id") == subscription_asset_id for a in info.get("assets", []))
        if not opted_in:
            curr_sp = algod.suggested_params()
            opt_txn = transaction.AssetOptInTxn(addr, curr_sp, subscription_asset_id)
            stxn = opt_txn.sign(sk)
            txid = algod.send_transaction(stxn)
            transaction.wait_for_confirmation(algod, txid, 4)

    # Opt into mUSD: vendorA..D, client1, client2
    for role in ["vendorA", "vendorB", "vendorC", "vendorD", "client1", "client2"]:
        addr = accounts[role]["address"]
        sk = mnemonic.to_private_key(accounts[role]["mnemonic"])
        info = algod.account_info(addr)
        opted_in = any(a.get("asset-id") == musd_asset_id for a in info.get("assets", []))
        if not opted_in:
            curr_sp = algod.suggested_params()
            opt_txn = transaction.AssetOptInTxn(addr, curr_sp, musd_asset_id)
            stxn = opt_txn.sign(sk)
            txid = algod.send_transaction(stxn)
            transaction.wait_for_confirmation(algod, txid, 4)

    # Send 1000 mUSD (1000*10**6 base units) from server to client1 and client2 only if balance < 100 mUSD
    server_addr = accounts["server"]["address"]
    server_sk = mnemonic.to_private_key(accounts["server"]["mnemonic"])
    for client_role in ["client1", "client2"]:
        c_addr = accounts[client_role]["address"]
        info = algod.account_info(c_addr)
        musd_bal = next((a.get("amount", 0) for a in info.get("assets", []) if a.get("asset-id") == musd_asset_id), 0)
        if musd_bal < 100 * 10**6:
            curr_sp = algod.suggested_params()
            send_txn = transaction.AssetTransferTxn(
                sender=server_addr,
                sp=curr_sp,
                receiver=c_addr,
                amt=1000 * 10**6,
                index=musd_asset_id,
            )
            stxn = send_txn.sign(server_sk)
            txid = algod.send_transaction(stxn)
            transaction.wait_for_confirmation(algod, txid, 4)

    # Write accounts.json
    data = {
        "network": network,
        "genesis_hash": gh,
        "algod_url": common.ALGOD_URL,
        "algod_token": common.TOKEN,
        "kmd_url": common.KMD_URL,
        "indexer_url": common.INDEXER_URL,
        "subscription_asset_id": int(subscription_asset_id),
        "musd_asset_id": int(musd_asset_id),
        "accounts": accounts,
    }

    with open(common.ACCOUNTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    os.chmod(common.ACCOUNTS_FILE, 0o600)

    # Print one line per role: role address ALGO balance mUSD balance (never mnemonics), then musd_asset_id
    for role in ROLES:
        addr = accounts[role]["address"]
        info = algod.account_info(addr)
        bal_micro = info.get("amount", 0)
        bal_algo = bal_micro / 1_000_000
        musd_base = next((a.get("amount", 0) for a in info.get("assets", []) if a.get("asset-id") == musd_asset_id), 0)
        musd_bal = musd_base / 1_000_000
        print(f"{role}: {addr} {bal_algo:.6f} ALGO {musd_bal:.6f} mUSD")
    print(f"musd_asset_id: {musd_asset_id}")


if __name__ == "__main__":
    main()
