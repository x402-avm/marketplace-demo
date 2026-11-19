#!/usr/bin/env python3
"""Fleet agent demo: one paying client calls domains and prints on-chain receipts."""

import argparse
import asyncio
import base64
import json
import os
import pathlib
import subprocess
import sys
import time
from typing import Any, Dict

# Paths
SERVERS_DIR = pathlib.Path(__file__).resolve().parents[1]
REPO_DIR = SERVERS_DIR.parent
CHAIN_DIR = REPO_DIR / "chain"
TOPOLOGY_FILE = SERVERS_DIR / "topology.json"
TEST_MATRIX_FILE = SERVERS_DIR / "tools" / "test_matrix.json"
ACCOUNTS_FILE = CHAIN_DIR / "accounts.json"
FIXTURES_DIR = SERVERS_DIR / "tests" / "fixtures"

SKIP_TOOLS = {"download_yt_video", "generate_image", "edit_image"}


def normalize_address(x: Any) -> str:
    if not x:
        return ""
    from algosdk import encoding
    if isinstance(x, bytes):
        if len(x) == 32:
            return encoding.encode_address(x)
        x = x.decode("utf-8", errors="replace")
    if isinstance(x, str):
        if len(x) == 58:
            return x
        try:
            raw = base64.b64decode(x)
            if len(raw) == 32:
                return encoding.encode_address(raw)
        except Exception:
            pass
    return str(x)


def needs_tmp(obj: Any) -> bool:
    if isinstance(obj, str):
        return "{TMP}" in obj
    if isinstance(obj, dict):
        return any(needs_tmp(v) for v in obj.values())
    if isinstance(obj, list):
        return any(needs_tmp(v) for v in obj)
    return False


def substitute_fixtures(obj: Any) -> Any:
    if isinstance(obj, str):
        return obj.replace("{FIX}", str(FIXTURES_DIR))
    if isinstance(obj, dict):
        return {k: substitute_fixtures(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [substitute_fixtures(v) for v in obj]
    return obj


def pick_case_for_domain(domain: str, test_matrix: Dict[str, Any]) -> Dict[str, Any]:
    cases = test_matrix.get(domain, {}).get("cases", [])
    for c in cases:
        if c.get("tool") in SKIP_TOOLS:
            continue
        if needs_tmp(c.get("args", {})):
            continue
        return c
    raise RuntimeError(f"No eligible test case found for domain '{domain}'")


async def run_demo(domains: list, payer_mode: str, start_domains: bool):
    from algosdk import account, mnemonic, transaction
    from algosdk.v2client import algod, indexer
    from ai_economy_sdk.client import paid_mcp_session

    cfg = json.loads(ACCOUNTS_FILE.read_text(encoding="utf-8"))
    topology = json.loads(TOPOLOGY_FILE.read_text(encoding="utf-8"))
    test_matrix = json.loads(TEST_MATRIX_FILE.read_text(encoding="utf-8"))

    algod_client = algod.AlgodClient(cfg["algod_token"], cfg["algod_url"])
    indexer_client = indexer.IndexerClient("", cfg.get("indexer_url", "http://localhost:8980"))
    server_addr = cfg["accounts"]["server"]["address"]

    # Setup payer account
    if payer_mode == "fresh":
        sys.path.insert(0, str(CHAIN_DIR))
        import common as chain_common
        disp_addr, disp_sk = chain_common.dispenser()
        payer_sk, payer_addr = account.generate_account()
        sp = algod_client.suggested_params()
        fund_txn = transaction.PaymentTxn(disp_addr, sp, payer_addr, 5_000_000)
        txid = algod_client.send_transaction(fund_txn.sign(disp_sk))
        transaction.wait_for_confirmation(algod_client, txid, 4)
        print(f"Payer: fresh account {payer_addr} funded with 5.0 ALGO")
    elif payer_mode in ("client1", "client2"):
        acc_info = cfg["accounts"][payer_mode]
        payer_addr = acc_info["address"]
        payer_sk = mnemonic.to_private_key(acc_info["mnemonic"])
        print(f"Payer: {payer_mode} ({payer_addr})")
    else:
        raise ValueError(f"Unknown payer mode: {payer_mode}")

    # Track initial balances
    server_initial_bal = algod_client.account_info(server_addr)["amount"]
    payer_initial_bal = algod_client.account_info(payer_addr)["amount"]

    receipts = []
    failed = False

    print("\n=== Agent Demo Run ===")
    for domain in domains:
        if domain not in topology:
            print(f"Error: domain '{domain}' not in topology.json", file=sys.stderr)
            failed = True
            continue

        case = pick_case_for_domain(domain, test_matrix)
        tool_name = case["tool"]
        raw_args = case.get("args", {})
        call_args = substitute_fixtures(raw_args)
        proxy_port = topology[domain]["proxy_ports"][0]
        url = f"http://127.0.0.1:{proxy_port}/sse"

        # Start domain if requested
        if start_domains:
            env = os.environ.copy()
            env["PAYMENTS"] = "on"
            if domain == "image_gen":
                env["FAST_TEST_MODE"] = env.get("FAST_TEST_MODE", "1")
                env["RUNTIME_WAIT"] = "600"
            cmd_up = [str(SERVERS_DIR / "tools" / "domainctl.sh"), "up", domain]
            res_up = subprocess.run(cmd_up, env=env, capture_output=True, text=True)
            if res_up.returncode != 0:
                print(f"Failed to start domain '{domain}': {res_up.stderr or res_up.stdout}", file=sys.stderr)
                failed = True
                continue

        start_round = algod_client.status()["last-round"]

        try:
            # Call tool through paid_mcp_session
            async with paid_mcp_session(
                url,
                payer_sk,
                cfg["network"],
                algod_url=cfg["algod_url"],
                algod_token=cfg["algod_token"],
            ) as session:
                timeout_sec = case.get("timeout", 120)
                res = await asyncio.wait_for(session.call_tool(tool_name, call_args), timeout=timeout_sec)
                text = "\n".join(getattr(c, "text", "") or "" for c in getattr(res, "content", []))
                clean_result = " ".join(text.split())[:60]
        except Exception as e:
            clean_result = f"<error: {e}>"[:60]
            print(f"Error calling {domain}.{tool_name}: {e}", file=sys.stderr)
            failed = True
            if start_domains:
                subprocess.run([str(SERVERS_DIR / "tools" / "domainctl.sh"), "down", domain], capture_output=True)
            continue

        # Wait for on-chain block confirmation
        current_round = algod_client.status()["last-round"]
        if current_round <= start_round:
            for _ in range(25):
                await asyncio.sleep(0.1)
                current_round = algod_client.status()["last-round"]
                if current_round > start_round:
                    break

        # Search on-chain payment
        found_txid = None
        found_round = None
        found_amount = None

        # Search indexer with retries
        for _ in range(15):
            try:
                res_idx = indexer_client.search_transactions(address=payer_addr, min_round=start_round + 1)
                for t in res_idx.get("transactions", []):
                    if t.get("tx-type") == "pay" and t.get("sender") == payer_addr:
                        pay_info = t.get("payment-transaction", {})
                        if pay_info.get("receiver") == server_addr:
                            found_txid = t.get("id")
                            found_round = t.get("confirmed-round")
                            found_amount = pay_info.get("amount", 0)
                            break
            except Exception:
                pass
            if found_txid:
                break
            await asyncio.sleep(0.2)

        # Fallback to direct algod block inspection
        if not found_txid:
            for r in range(start_round + 1, current_round + 1):
                try:
                    blk = algod_client.block_info(r)
                    for t in blk.get("block", {}).get("txns", []):
                        tb = t.get("txn", {})
                        if tb.get("type") == "pay":
                            snd = normalize_address(tb.get("snd"))
                            rcv = normalize_address(tb.get("rcv"))
                            if snd == payer_addr and rcv == server_addr:
                                found_amount = tb.get("amt", 0)
                                found_round = r
                                # Attempt indexer lookup for this specific round
                                try:
                                    res_idx = indexer_client.search_transactions(min_round=r, max_round=r)
                                    for itx in res_idx.get("transactions", []):
                                        if itx.get("sender") == payer_addr:
                                            found_txid = itx.get("id")
                                            break
                                except Exception:
                                    pass
                                if not found_txid:
                                    found_txid = f"rnd-{r}-amt-{found_amount}"
                                break
                except Exception:
                    pass
                if found_txid:
                    break

        if not found_txid:
            print(f"Warning: No on-chain payment found for {domain} (rounds {start_round+1}..{current_round})", file=sys.stderr)
            failed = True
            found_txid = "MISSING"
            found_round = "-"
            found_amount = 0

        # Print receipt line:
        # <domain> | <tool> | price <p> | txid <id> | round <r> | result: <first 60 chars of output>
        receipt_line = f"{domain} | {tool_name} | price {found_amount} | txid {found_txid} | round {found_round} | result: {clean_result}"
        print(receipt_line)
        receipts.append({
            "domain": domain,
            "tool": tool_name,
            "amount": found_amount,
            "txid": found_txid,
            "round": found_round,
            "result": clean_result,
            "line": receipt_line,
        })

        # Stop domain if requested
        if start_domains:
            cmd_down = [str(SERVERS_DIR / "tools" / "domainctl.sh"), "down", domain]
            subprocess.run(cmd_down, capture_output=True, check=True)

    # Compute totals
    server_final_bal = algod_client.account_info(server_addr)["amount"]
    payer_final_bal = algod_client.account_info(payer_addr)["amount"]
    server_net = server_final_bal - server_initial_bal
    total_paid_microalgos = sum(r["amount"] for r in receipts)
    total_paid_algo = total_paid_microalgos / 1_000_000

    print("\n=== Totals ===")
    print(f"Number of paid calls: {len(receipts)}")
    print(f"Total paid by payer: {total_paid_microalgos} microAlgos ({total_paid_algo:.6f} ALGO)")
    print(f"Server net income: {server_net} microAlgos ({server_net / 1e6:.6f} ALGO)")

    # Run explorer.py verify
    verify_proc = subprocess.run(
        [sys.executable, str(CHAIN_DIR / "explorer.py"), "verify"],
        cwd=str(CHAIN_DIR),
        capture_output=True,
        text=True,
    )
    last_line = verify_proc.stdout.strip().splitlines()[-1] if verify_proc.stdout.strip() else ""
    print(f"Explorer verify: {last_line}")

    if verify_proc.returncode != 0:
        print(f"Explorer verification failed: {verify_proc.stderr}", file=sys.stderr)
        failed = True

    if failed:
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Fleet Agent Demo: Paying client for MCP servers")
    topology = json.loads(TOPOLOGY_FILE.read_text(encoding="utf-8"))
    default_domains = [d for d in topology.keys() if d != "image_gen"]

    parser.add_argument(
        "--domains",
        nargs="+",
        default=default_domains,
        help="Domains to invoke (default: all in topology.json except image_gen)",
    )
    parser.add_argument(
        "--payer",
        choices=["client1", "client2", "fresh"],
        default="fresh",
        help="Payer account mode (default: fresh funded from dispenser)",
    )
    parser.add_argument(
        "--start",
        action="store_true",
        default=False,
        help="Start each domain with PAYMENTS=on via domainctl.sh up before calling and down after",
    )

    args = parser.parse_args()
    asyncio.run(run_demo(args.domains, args.payer, args.start))


if __name__ == "__main__":
    main()
