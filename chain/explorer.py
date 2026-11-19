#!/usr/bin/env python3
"""Algorand LocalNet Block Explorer and CLI tool."""

import argparse
import base64
import datetime
import json
import sys
import time
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)
from algosdk import mnemonic, transaction
import common


def strip_blk(h: str) -> str:
    """Strip leading 'blk-' from a block or prev hash string."""
    if not h or h == "-":
        return "-"
    return str(h).removeprefix("blk-")


def cmd_status(args):
    algod = common.algod_client()
    kmd = common.kmd_client()
    status = algod.status()
    params = algod.suggested_params()
    wallets = kmd.list_wallets()

    gh = params.gh
    print(f"Network: algorand:{gh}")
    print(f"Genesis Hash: {gh}")
    print(f"Last Round: {status.get('last-round')}")
    tslr_ns = status.get("time-since-last-round", 0)
    tslr_s = tslr_ns / 1e9
    print(f"Time Since Last Block: {tslr_s:.1f}s")
    print(f"KMD Wallets: {len(wallets)}")


def cmd_wallets(args):
    algod = common.algod_client()
    kmd = common.kmd_client()

    print("=== KMD Wallets ===")
    wallets = kmd.list_wallets()
    for w in wallets:
        w_name = w.get("name", "unknown")
        w_id = w.get("id", "")
        print(f"Wallet: {w_name} (ID: {w_id})")
        try:
            handle = kmd.init_wallet_handle(w_id, "")
            try:
                keys = kmd.list_keys(handle)
                for k in keys:
                    info = algod.account_info(k)
                    bal = info.get("amount", 0)
                    print(f"  Address: {k} | Balance: {bal} microAlgos ({bal/1e6:.6f} ALGO)")
            finally:
                kmd.release_wallet_handle(handle)
        except Exception as e:
            print(f"  [Error accessing wallet keys: {e}]")

    print("\n=== Roles (from accounts.json) ===")
    if common.ACCOUNTS_FILE.exists():
        try:
            accounts_data = common.load_accounts()
            for role, data in accounts_data.get("accounts", {}).items():
                addr = data.get("address")
                try:
                    info = algod.account_info(addr)
                    bal = info.get("amount", 0)
                    assets = info.get("assets", [])
                    print(f"Role: {role} | Address: {addr} | Balance: {bal} microAlgos ({bal/1e6:.6f} ALGO) | Assets: {assets}")
                except Exception as e:
                    print(f"Role: {role} | Address: {addr} | [Error fetching info: {e}]")
        except Exception as e:
            print(f"[Error reading accounts.json: {e}]")
    else:
        print("[accounts.json not found]")


def get_block_header(algod, r: int):
    try:
        h_resp = algod.algod_request("GET", f"/blocks/{r}/hash")
        raw_hash = h_resp.get("blockHash", "-")
        block_hash = strip_blk(raw_hash)
    except Exception:
        block_hash = "-"

    binfo = algod.block_info(r)
    block_data = binfo.get("block", {}) if isinstance(binfo, dict) else {}
    raw_prev = block_data.get("prev", "-")
    prev_hash = strip_blk(raw_prev)

    ts = block_data.get("ts")
    if ts is not None:
        ts_iso = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc).isoformat()
    else:
        ts_iso = "-"

    txn_count = len(block_data.get("txns", []))

    proposer = "-"
    if isinstance(binfo, dict):
        cert = binfo.get("cert")
        if isinstance(cert, dict):
            prop = cert.get("prop")
            if isinstance(prop, dict):
                proposer = prop.get("oprop", "-")

    return {
        "round": r,
        "hash": block_hash,
        "prev": prev_hash,
        "timestamp": ts_iso,
        "txns_count": txn_count,
        "proposer": proposer,
        "block_data": block_data,
    }


def cmd_blocks(args):
    algod = common.algod_client()
    status = algod.status()
    last_round = status.get("last-round", 0)

    n = args.num
    start_round = max(0, last_round - n + 1)
    rounds = list(range(last_round, start_round - 1, -1))

    for r in rounds:
        hdr = get_block_header(algod, r)
        print(f"Round {hdr['round']:<4} | Hash: {hdr['hash']} | Prev: {hdr['prev']} | TS: {hdr['timestamp']} | Txns: {hdr['txns_count']} | Proposer: {hdr['proposer']}")


def cmd_block(args):
    algod = common.algod_client()
    r = args.round
    hdr = get_block_header(algod, r)
    print(f"Round: {hdr['round']}")
    print(f"Block Hash: {hdr['hash']}")
    print(f"Prev Hash: {hdr['prev']}")
    print(f"Timestamp: {hdr['timestamp']}")
    print(f"Txns Count: {hdr['txns_count']}")
    print(f"Proposer: {hdr['proposer']}")

    txns = hdr["block_data"].get("txns", [])
    if txns:
        print("Transactions:")
        for idx, t in enumerate(txns):
            txn_dict = t.get("txn", {}) if isinstance(t, dict) else {}
            t_type = txn_dict.get("type", "-")
            snd = txn_dict.get("snd", "-")
            rcv = txn_dict.get("rcv") or txn_dict.get("arcv") or "-"
            amt = txn_dict.get("amt") if "amt" in txn_dict else txn_dict.get("aamt", 0)
            print(f"  [{idx}] Type: {t_type} | Sender: {snd} | Receiver: {rcv} | Amount: {amt}")


def cmd_verify(args):
    algod = common.algod_client()
    status = algod.status()
    last_round = status.get("last-round", 0)

    R1 = args.to_round if args.to_round is not None else last_round
    R0 = args.from_round if args.from_round is not None else max(0, R1 - 200)

    if R0 >= R1:
        print(f"OK hash-chain intact for rounds {R0}..{R1} (no rounds to verify)")
        sys.exit(0)

    for r in range(R0 + 1, R1 + 1):
        binfo = algod.block_info(r)
        prev_raw = str(binfo.get("block", {}).get("prev", ""))
        prev_norm = strip_blk(prev_raw)

        h_resp = algod.algod_request("GET", f"/blocks/{r-1}/hash")
        hash_raw = str(h_resp.get("blockHash", ""))
        hash_norm = strip_blk(hash_raw)

        if prev_norm != hash_norm:
            print(f"BROKEN hash-chain at round {r}: block prev '{prev_norm}' != round {r-1} hash '{hash_norm}'")
            sys.exit(1)

    print(f"OK hash-chain intact for rounds {R0}..{R1}")
    sys.exit(0)


def cmd_stats(args):
    algod = common.algod_client()
    status = algod.status()
    last_round = status.get("last-round", 0)

    n = args.num
    start_round = max(0, last_round - n + 1)
    rounds = list(range(start_round, last_round + 1))
    num_blocks = len(rounds)

    total_txns = 0
    type_counts = {}
    timestamps = []

    for r in rounds:
        binfo = algod.block_info(r)
        block_data = binfo.get("block", {}) if isinstance(binfo, dict) else {}
        ts = block_data.get("ts")
        if ts is not None:
            timestamps.append(ts)
        txns = block_data.get("txns", [])
        total_txns += len(txns)
        for t in txns:
            txn_dict = t.get("txn", {}) if isinstance(t, dict) else {}
            t_type = txn_dict.get("type", "unknown")
            type_counts[t_type] = type_counts.get(t_type, 0) + 1

    avg_txns = total_txns / num_blocks if num_blocks > 0 else 0.0

    diffs = [timestamps[i] - timestamps[i - 1] for i in range(1, len(timestamps))]
    avg_secs = sum(diffs) / len(diffs) if diffs else 0.0

    print(f"First Round: {start_round}")
    print(f"Last Round: {last_round}")
    print(f"Number of Blocks: {num_blocks}")
    print(f"Total Transactions: {total_txns}")
    print(f"Txns per Block (avg): {avg_txns:.2f}")
    print(f"Average Seconds Between Blocks: {avg_secs:.1f}s")
    print("Transactions by Type:")
    if type_counts:
        for t_type, count in sorted(type_counts.items()):
            print(f"  {t_type}: {count}")
    else:
        print("  (none)")
    print("Consensus: Algorand Pure Proof-of-Stake (no mining). LocalNet dev mode creates one block per transaction group.")


def cmd_txns(args):
    indexer = common.indexer_client()
    target = args.role_or_address
    limit = args.num

    addr = target
    if common.ACCOUNTS_FILE.exists():
        try:
            accounts_data = common.load_accounts()
            accounts_dict = accounts_data.get("accounts", {})
            if target in accounts_dict:
                addr = accounts_dict[target].get("address", target)
        except Exception:
            pass

    res = indexer.search_transactions(address=addr, limit=limit)
    txns = res.get("transactions", [])
    if not txns:
        print(f"No transactions found for {target} ({addr})")
        return

    for t in txns:
        txid = t.get("id", "-")
        rnd = t.get("confirmed-round", "-")
        txtype = t.get("tx-type", "-")
        snd = t.get("sender", "-")

        if txtype == "pay":
            rcv = t.get("payment-transaction", {}).get("receiver", "-")
            amt = t.get("payment-transaction", {}).get("amount", 0)
        elif txtype == "axfer":
            rcv = t.get("asset-transfer-transaction", {}).get("receiver", "-")
            amt = t.get("asset-transfer-transaction", {}).get("amount", 0)
        else:
            rcv = "-"
            amt = 0

        note_raw = t.get("note")
        if note_raw:
            try:
                note = base64.b64decode(note_raw).decode("utf-8", errors="replace")
            except Exception:
                note = "<binary>"
        else:
            note = "-"

        print(f"TxID: {txid} | Round: {rnd} | Type: {txtype} | Sender: {snd} | Receiver: {rcv} | Amount: {amt} | Note: {note}")


def cmd_send(args):
    algod = common.algod_client()
    accounts_data = common.load_accounts()
    accounts_dict = accounts_data.get("accounts", {})

    from_role = args.from_role
    if from_role not in accounts_dict:
        print(f"Error: role '{from_role}' not found in accounts.json", file=sys.stderr)
        sys.exit(1)

    from_info = accounts_dict[from_role]
    from_addr = from_info["address"]
    from_sk = mnemonic.to_private_key(from_info["mnemonic"])

    to_target = args.to_target
    if to_target in accounts_dict:
        to_addr = accounts_dict[to_target]["address"]
    else:
        to_addr = to_target

    microalgos = int(args.microalgos)
    note_bytes = args.note.encode("utf-8") if args.note else None

    sp = algod.suggested_params()
    ptxn = transaction.PaymentTxn(from_addr, sp, to_addr, microalgos, note=note_bytes)
    stxn = ptxn.sign(from_sk)
    txid = algod.send_transaction(stxn)
    confirmed = transaction.wait_for_confirmation(algod, txid, 4)
    rnd = confirmed.get("confirmed-round")
    print(f"Transaction sent: txid={txid} confirmed_round={rnd}")


def cmd_watch(args):
    algod = common.algod_client()
    status = algod.status()
    current_round = status.get("last-round", 0)
    print(f"Watching for new blocks (latest round: {current_round})... Press Ctrl-C to stop.", flush=True)

    try:
        while True:
            time.sleep(2)
            st = algod.status()
            latest = st.get("last-round", 0)
            if latest > current_round:
                for r in range(current_round + 1, latest + 1):
                    try:
                        raw_h = algod.algod_request("GET", f"/blocks/{r}/hash").get("blockHash", "-")
                        h = strip_blk(raw_h)
                    except Exception:
                        h = "-"
                    binfo = algod.block_info(r).get("block", {})
                    cnt = len(binfo.get("txns", []))
                    print(f"Round {r}: hash {h}, txns: {cnt}", flush=True)
                current_round = latest
    except KeyboardInterrupt:
        sys.exit(0)


def main():
    parser = argparse.ArgumentParser(description="Algorand LocalNet Explorer")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # status
    subparsers.add_parser("status", help="Show LocalNet status")

    # wallets
    subparsers.add_parser("wallets", help="List KMD and role wallets")

    # blocks
    p_blocks = subparsers.add_parser("blocks", help="List recent blocks")
    p_blocks.add_argument("-n", "--num", type=int, default=10, help="Number of rounds")

    # block
    p_block = subparsers.add_parser("block", help="Show block details")
    p_block.add_argument("round", type=int, help="Block round")

    # verify
    p_verify = subparsers.add_parser("verify", help="Verify hash-chain integrity")
    p_verify.add_argument("--from", dest="from_round", type=int, default=None, help="Start round")
    p_verify.add_argument("--to", dest="to_round", type=int, default=None, help="End round")

    # stats
    p_stats = subparsers.add_parser("stats", help="Compute block and transaction statistics")
    p_stats.add_argument("-n", "--num", type=int, default=50, help="Number of recent blocks to analyze")

    # txns
    p_txns = subparsers.add_parser("txns", help="Search transactions for role or address")
    p_txns.add_argument("role_or_address", type=str, help="Role name or address")
    p_txns.add_argument("-n", "--num", type=int, default=10, help="Limit number of txns")

    # send
    p_send = subparsers.add_parser("send", help="Send microAlgos payment")
    p_send.add_argument("from_role", type=str, help="Sender role")
    p_send.add_argument("to_target", type=str, help="Receiver role or address")
    p_send.add_argument("microalgos", type=int, help="Amount in microAlgos")
    p_send.add_argument("--note", type=str, default=None, help="Optional note")

    # watch
    subparsers.add_parser("watch", help="Watch for new blocks")

    args = parser.parse_args()

    dispatch = {
        "status": cmd_status,
        "wallets": cmd_wallets,
        "blocks": cmd_blocks,
        "block": cmd_block,
        "verify": cmd_verify,
        "stats": cmd_stats,
        "txns": cmd_txns,
        "send": cmd_send,
        "watch": cmd_watch,
    }

    dispatch[args.subcommand](args)


if __name__ == "__main__":
    main()
