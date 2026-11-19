#!/usr/bin/env python3
"""
Marketplace activity simulator: real buyers paying real vendors on LocalNet.
CLI: simulate_market.py --buyers N --calls M --domains tts,sandbox_mcp,... --seed S --dry-run
"""

import argparse
import asyncio
import json
import os
from pathlib import Path
import random
import re
import socket
import sys
import time
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)
from algosdk import account, mnemonic, transaction
from algosdk.v2client import algod, indexer

REPO_DIR = Path(__file__).resolve().parents[1]
CHAIN_DIR = REPO_DIR / "chain"
SERVERS_DIR = REPO_DIR / "servers"
MARKETPLACE_FILE = SERVERS_DIR / "marketplace.json"
TEST_MATRIX_FILE = SERVERS_DIR / "tools" / "test_matrix.json"
FIXTURES_DIR = SERVERS_DIR / "tests" / "fixtures"
TMP_DIR = SERVERS_DIR / "tests" / "outputs" / "simulate"
os.makedirs(TMP_DIR, exist_ok=True)

if str(CHAIN_DIR) not in sys.path:
    sys.path.insert(0, str(CHAIN_DIR))

import common
from ai_economy_sdk.client import paid_mcp_session


def subst_args(args_dict, port, fixtures_dir, tmp_dir):
    """Recursively replace {FIX}, {TMP}, {PORT} placeholders in test args."""
    def _sub(val):
        if isinstance(val, str):
            return (
                val.replace("{FIX}", str(fixtures_dir))
                .replace("{TMP}", str(tmp_dir))
                .replace("{PORT}", str(port))
            )
        elif isinstance(val, dict):
            return {k: _sub(v) for k, v in val.items()}
        elif isinstance(val, list):
            return [_sub(v) for v in val]
        return val

    return _sub(args_dict)


def get_positive_case_for_tool(test_matrix, domain, tool_name, port, return_spec=False):
    """Retrieve the first positive test case for a given tool from test_matrix.json."""
    cases = test_matrix.get(domain, {}).get("cases", [])
    for c in cases:
        if c.get("tool") == tool_name and not c.get("allow_error") and not c.get("must_error"):
            cargs = c.get("args", {})
            args = subst_args(cargs, port, FIXTURES_DIR, TMP_DIR)
            if return_spec:
                return c.get("id", "default"), args, c
            return c.get("id", "default"), args
    # Fallback to any case for the tool if no explicitly positive case marked
    for c in cases:
        if c.get("tool") == tool_name:
            cargs = c.get("args", {})
            args = subst_args(c.get("args", {}), port, FIXTURES_DIR, TMP_DIR)
            if return_spec:
                return c.get("id", "default"), args, c
            return c.get("id", "default"), args
    if return_spec:
        return "empty", {}, {}
    return "empty", {}


def is_port_open(port: int, host: str = "127.0.0.1", timeout: float = 0.5) -> bool:
    """Check if a TCP port is open."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            return s.connect_ex((host, port)) == 0
    except Exception:
        return False


def build_simulation_plan(
    buyers_data: list[dict],
    candidate_listings: list[dict],
    test_matrix: dict,
    num_calls: int,
    seed: int | None = None,
) -> list[dict]:
    """Generate a deterministic plan of calls using seeded RNG."""
    rng = random.Random(seed) if seed is not None else random.Random()
    plan = []
    for i in range(num_calls):
        buyer = rng.choice(buyers_data)
        listing = rng.choice(candidate_listings)
        available_tools = sorted(listing.get("prices", {}).keys())
        if not available_tools:
            continue
        tool_name = rng.choice(available_tools)
        price = listing["prices"][tool_name]
        case_id, tool_args, case_spec = get_positive_case_for_tool(
            test_matrix, listing["domain"], tool_name, listing["port"], return_spec=True
        )
        plan.append({
            "call_index": i + 1,
            "buyer": buyer,
            "listing": listing,
            "domain": listing["domain"],
            "proxy_index": listing["proxy_index"],
            "port": listing["port"],
            "vendor": listing["vendor"],
            "asset": listing["asset"],
            "multiplier": listing["multiplier"],
            "tool": tool_name,
            "price": price,
            "case_id": case_id,
            "args": tool_args,
            "case_spec": case_spec,
        })
    return plan


def get_buyer_txids(idx_client: indexer.IndexerClient, buyer_addr: str) -> set[str]:
    """Retrieve all transaction IDs sent by buyer from indexer."""
    try:
        res = idx_client.search_transactions(address=buyer_addr, limit=50)
        return {t["id"] for t in res.get("transactions", []) if t.get("sender") == buyer_addr}
    except Exception:
        return set()


async def run_simulation(args):
    marketplace = json.loads(MARKETPLACE_FILE.read_text(encoding="utf-8"))
    test_matrix = json.loads(TEST_MATRIX_FILE.read_text(encoding="utf-8"))
    chosen_domains = [d.strip() for d in args.domains.split(",") if d.strip()]

    # Candidate listings from chosen domains
    candidate_listings = [
        l for l in marketplace.get("listings", []) if l.get("domain") in chosen_domains
    ]
    if not candidate_listings:
        print(f"Error: No listings found for domains: {chosen_domains}")
        sys.exit(1)

    # --- DRY RUN MODE ---
    if args.dry_run:
        simulated_buyers = [
            {"index": i, "address": f"BUYER_{i+1:02d}", "sk": None}
            for i in range(args.buyers)
        ]
        plan = build_simulation_plan(
            simulated_buyers, candidate_listings, test_matrix, args.calls, seed=args.seed
        )

        print("=" * 90)
        print(f"DRY-RUN MARKETPLACE ACTIVITY SIMULATION (seed={args.seed})")
        print("=" * 90)
        print(f"Configured: {args.buyers} buyers, {args.calls} calls, domains: {chosen_domains}")
        print(f"Eligible listings: {len(candidate_listings)} across {len(chosen_domains)} domains")
        print("\nSIMULATION CALL PLAN:")
        print(f"{'#':<4} {'Buyer':<10} {'Listing':<18} {'Vendor':<10} {'Asset':<6} {'Price':<12} {'Tool'}")
        print("-" * 90)
        vendor_totals = {v: {"calls": 0, "algo": 0, "musd": 0} for v in ["vendorA", "vendorB", "vendorC", "vendorD"]}
        for item in plan:
            b_label = item["buyer"]["address"]
            l_label = f"{item['listing']['id']} ({item['port']})"
            v = item["vendor"]
            a = item["asset"]
            p = item["price"]
            t = item["tool"]
            vendor_totals[v]["calls"] += 1
            if a == "ALGO":
                vendor_totals[v]["algo"] += p
            else:
                vendor_totals[v]["musd"] += p
            print(f"{item['call_index']:<4} {b_label:<10} {l_label:<18} {v:<10} {a:<6} {p:<12} {t}")

        print("-" * 90)
        print("DRY-RUN PROJECTED VENDOR TOTALS:")
        print(f"{'Vendor':<10} {'Calls':<8} {'Projected ALGO':<18} {'Projected mUSD':<18}")
        print("-" * 60)
        for v in sorted(vendor_totals.keys()):
            vt = vendor_totals[v]
            print(f"{v:<10} {vt['calls']:<8} {vt['algo']:<18} {vt['musd']:<18}")
        print("-" * 60)
        print("[DRY-RUN] No transactions submitted to chain.")
        return

    # --- LIVE MODE ---
    algod_client = common.algod_client()
    indexer_client = common.indexer_client()
    accounts_data = common.load_accounts()
    musd_id = int(accounts_data["musd_asset_id"])
    network = accounts_data["network"]

    # Filter to only listings that are ONLINE (port open)
    online_listings = [l for l in candidate_listings if is_port_open(l["port"])]
    if not online_listings:
        print(f"Error: No online proxies found for domains {chosen_domains}.")
        print("Ensure servers are running with: domainctl.sh up <domain>")
        sys.exit(1)

    print(f"Found {len(online_listings)}/{len(candidate_listings)} online listings for domains {chosen_domains}.")

    # 1. Generate N fresh buyer accounts in memory
    print(f"\n1. Creating and funding {args.buyers} fresh buyer accounts...")
    buyers = []
    disp_addr, disp_sk = common.dispenser()
    server_addr = accounts_data["accounts"]["server"]["address"]
    server_sk = mnemonic.to_private_key(accounts_data["accounts"]["server"]["mnemonic"])

    for i in range(args.buyers):
        sk, addr = account.generate_account()
        buyers.append({"index": i, "address": addr, "sk": sk})

    # Fund each 20 ALGO (20_000_000 microAlgos) from KMD dispenser
    curr_sp = algod_client.suggested_params()
    for b in buyers:
        ptxn = transaction.PaymentTxn(disp_addr, curr_sp, b["address"], 20_000_000)
        stxn = ptxn.sign(disp_sk)
        txid = algod_client.send_transaction(stxn)
        transaction.wait_for_confirmation(algod_client, txid, 4)

    # Opt each buyer into mUSD
    for b in buyers:
        curr_sp = algod_client.suggested_params()
        opt_txn = transaction.AssetOptInTxn(b["address"], curr_sp, musd_id)
        stxn = opt_txn.sign(b["sk"])
        txid = algod_client.send_transaction(stxn)
        transaction.wait_for_confirmation(algod_client, txid, 4)

    # Send 200 mUSD (200 * 10^6 base units) from server to each buyer
    for b in buyers:
        curr_sp = algod_client.suggested_params()
        send_txn = transaction.AssetTransferTxn(
            sender=server_addr,
            sp=curr_sp,
            receiver=b["address"],
            amt=200 * 10**6,
            index=musd_id,
        )
        stxn = send_txn.sign(server_sk)
        txid = algod_client.send_transaction(stxn)
        transaction.wait_for_confirmation(algod_client, txid, 4)

    print(f"   -> All {args.buyers} buyers funded with 20 ALGO and 200 mUSD.")

    # 2. Record vendor balances BEFORE
    vendors = ["vendorA", "vendorB", "vendorC", "vendorD"]
    balances_before = {}
    for v in vendors:
        v_addr = accounts_data["accounts"][v]["address"]
        info = algod_client.account_info(v_addr)
        bal_algo = info.get("amount", 0)
        bal_musd = next((a.get("amount", 0) for a in info.get("assets", []) if a.get("asset-id") == musd_id), 0)
        balances_before[v] = {
            "address": v_addr,
            "algo": bal_algo,
            "musd": bal_musd,
        }

    # 3. Build simulation plan
    plan = build_simulation_plan(buyers, online_listings, test_matrix, args.calls, seed=args.seed)

    # 4. Execute M calls
    print(f"\n2. Executing {len(plan)} paid MCP calls across {len(online_listings)} listings...")
    call_records = []

    for item in plan:
        buyer = item["buyer"]
        listing = item["listing"]
        tool_name = item["tool"]
        tool_args = item["args"]
        port = listing["port"]
        sse_url = f"http://127.0.0.1:{port}/sse"

        seen_txids = get_buyer_txids(indexer_client, buyer["address"])
        text = ""
        err_msg = ""
        res = None
        is_error = False
        is_ok = False
        try:
            async with paid_mcp_session(
                sse_url=sse_url,
                private_key=buyer["sk"],
                network=network,
                algod_url=common.ALGOD_URL,
                algod_token=common.TOKEN,
                timeout=30.0,
            ) as session:
                res = await session.call_tool(tool_name, tool_args)
                is_error = getattr(res, "isError", False)
                if res and getattr(res, "content", None):
                    text = "\n".join(getattr(c, "text", "") or "" for c in res.content)
                is_ok = not is_error
        except Exception as e:
            is_error = True
            is_ok = False
            err_msg = str(e)
            text = f"<exception {type(e).__name__}: {e}>"

        # Search indexer for the new payment transaction
        txid = None
        for _ in range(10):
            current_txids = get_buyer_txids(indexer_client, buyer["address"])
            diff = current_txids - seen_txids
            if diff:
                txid = sorted(list(diff))[-1]
                break
            if is_error and not res:
                break
            time.sleep(0.3)

        # Output validation and status determination
        case_spec = item.get("case_spec", {})
        expect_regexes = case_spec.get("expect", [])
        if isinstance(expect_regexes, str):
            expect_regexes = [expect_regexes]
        reject_regexes = case_spec.get("reject", [])
        if isinstance(reject_regexes, str):
            reject_regexes = [reject_regexes]

        combined_error_text = f"{text} {err_msg}"
        status = "FAIL"
        reason = ""

        if is_error:
            if "sandbox isolation unavailable" in combined_error_text:
                status = "SKIP-ENV"
                reason = "sandbox isolation unavailable"
            else:
                status = "FAIL"
                reason = err_msg or text or "tool returned isError=True"
        else:
            reasons = []
            for rx in expect_regexes:
                if not re.search(rx, text, re.S):
                    reasons.append(f"expected /{rx}/")
            for rx in reject_regexes:
                if re.search(rx, text, re.S):
                    reasons.append(f"rejected /{rx}/ matched")
            if reasons:
                status = "FAIL"
                reason = "; ".join(reasons)
            else:
                status = "PASS"
                reason = ""

        call_records.append({
            "call_index": item["call_index"],
            "buyer": buyer["address"],
            "listing": listing["id"],
            "vendor": listing["vendor"],
            "asset": listing["asset"],
            "tool": tool_name,
            "price": item["price"],
            "txid": txid or "not_found",
            "ok": (status == "PASS"),
            "status": status,
            "isError": is_error,
            "error": reason,
            "text": text,
        })
        err_extra = f" ({reason})" if reason else ""
        print(f"   [{item['call_index']:02d}/{args.calls:02d}] {status:<8} Listing={listing['id']} Vendor={listing['vendor']} Tool={tool_name} Price={item['price']} {listing['asset']} TxID={txid or 'not_found'}{err_extra}")

    # 5. Record vendor balances AFTER
    balances_after = {}
    for v in vendors:
        v_addr = accounts_data["accounts"][v]["address"]
        info = algod_client.account_info(v_addr)
        bal_algo = info.get("amount", 0)
        bal_musd = next((a.get("amount", 0) for a in info.get("assets", []) if a.get("asset-id") == musd_id), 0)
        balances_after[v] = {
            "address": v_addr,
            "algo": bal_algo,
            "musd": bal_musd,
        }

    # 6. Reconcile records vs on-chain deltas
    vendor_stats = {v: {"calls": 0, "revenue_algo": 0, "revenue_musd": 0} for v in vendors}
    for rec in call_records:
        if rec["txid"] != "not_found":
            v = rec["vendor"]
            vendor_stats[v]["calls"] += 1
            if rec["asset"] == "ALGO":
                vendor_stats[v]["revenue_algo"] += rec["price"]
            elif rec["asset"] == "mUSD":
                vendor_stats[v]["revenue_musd"] += rec["price"]

    reconciled = True
    mismatches = []

    print("\n" + "=" * 105)
    print("MARKETPLACE SIMULATION RECONCILIATION TABLE")
    print("=" * 105)
    print(f"{'Vendor':<10} {'Calls':<6} {'Recv ALGO':<12} {'Recv mUSD':<12} {'ALGO (Before -> After = Delta)':<36} {'mUSD (Before -> After = Delta)':<32}")
    print("-" * 105)

    for v in vendors:
        c = vendor_stats[v]["calls"]
        rev_algo = vendor_stats[v]["revenue_algo"]
        rev_musd = vendor_stats[v]["revenue_musd"]
        fees_paid = c * 2000

        expected_algo_delta = rev_algo - fees_paid
        expected_musd_delta = rev_musd

        actual_algo_delta = balances_after[v]["algo"] - balances_before[v]["algo"]
        actual_musd_delta = balances_after[v]["musd"] - balances_before[v]["musd"]

        if actual_algo_delta != expected_algo_delta:
            reconciled = False
            mismatches.append(
                f"{v} ALGO mismatch: actual {actual_algo_delta} != expected {expected_algo_delta} (rev={rev_algo}, fees={fees_paid})"
            )
        if actual_musd_delta != expected_musd_delta:
            reconciled = False
            mismatches.append(
                f"{v} mUSD mismatch: actual {actual_musd_delta} != expected {expected_musd_delta} (rev={rev_musd})"
            )

        algo_str = f"{balances_before[v]['algo']} -> {balances_after[v]['algo']} ({actual_algo_delta:+d})"
        musd_str = f"{balances_before[v]['musd']} -> {balances_after[v]['musd']} ({actual_musd_delta:+d})"
        print(f"{v:<10} {c:<6} {rev_algo:<12} {rev_musd:<12} {algo_str:<36} {musd_str:<32}")

    print("-" * 105)

    if not reconciled:
        print("MISMATCH: " + "; ".join(mismatches))
        sys.exit(1)

    print("RECONCILED")

    if any(r["status"] == "FAIL" for r in call_records):
        print("\nSIMULATION FAILED: One or more calls failed validation.")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Marketplace activity simulator on LocalNet")
    parser.add_argument("--buyers", type=int, default=5, help="Number of buyer accounts to generate (default 5)")
    parser.add_argument("--calls", type=int, default=20, help="Number of paid MCP calls to execute (default 20)")
    parser.add_argument(
        "--domains",
        type=str,
        default="tts,sandbox_mcp,latex_mcp,invoice_mcp",
        help="Comma-separated list of service domains (default tts,sandbox_mcp,latex_mcp,invoice_mcp)"
    )
    parser.add_argument("--seed", type=int, default=None, help="Random seed for deterministic call planning")
    parser.add_argument("--dry-run", action="store_true", help="Print simulation plan without executing transactions")

    args = parser.parse_args()
    asyncio.run(run_simulation(args))


if __name__ == "__main__":
    main()
