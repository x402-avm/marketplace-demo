#!/usr/bin/env python3
"""Functional probe for one MCP domain.

Usage (run with the DOMAIN's own venv python, servers must be up via tools/domainctl.sh):
    <domain>/venv/bin/python tools/probe.py <domain> [--port P] [--json OUT]

For every proxy port of the domain (from topology.json) it:
  1. connects over SSE, lists tools, checks every tool named in the matrix exists;
  2. calls each case in tools/test_matrix.json and checks the result STRICTLY:
     expect (regex, all must match), reject (regex, none may match), isError must be False
     (unless "allow_error": true), must_error: true -> the call must come back with isError=True,
     artifacts (output files must exist, be non-trivial, have the
     right magic bytes, optional pdf_text / contains / zip_entries / duration / image_size).
Exit code 0 only if every check on every port passes. Placeholders: {FIX} fixtures dir, {TMP} per-domain
temp output dir, {PORT} current proxy port.
"""
import argparse, asyncio, json, os, re, shutil, struct, subprocess, sys, zipfile
from pathlib import Path

SERVERS = Path(__file__).resolve().parent.parent
FIX = SERVERS / "tests" / "fixtures"
MAGIC = {
    ".pdf": [b"%PDF"], ".png": [b"\x89PNG"], ".jpg": [b"\xff\xd8"], ".jpeg": [b"\xff\xd8"],
    ".wav": [b"RIFF"], ".zip": [b"PK"], ".webm": [b"\x1aE\xdf\xa3"], ".mkv": [b"\x1aE\xdf\xa3"],
    ".mp3": [b"ID3", b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"], ".gif": [b"GIF8"], ".webp": [b"RIFF"],
}


def subst(obj, port, tmp):
    if isinstance(obj, str):
        return obj.replace("{FIX}", str(FIX)).replace("{TMP}", str(tmp)).replace("{PORT}", str(port))
    if isinstance(obj, list):
        return [subst(x, port, tmp) for x in obj]
    if isinstance(obj, dict):
        return {k: subst(v, port, tmp) for k, v in obj.items()}
    return obj


def check_artifact(spec, text, domain_dir):
    """Return list of failure strings for one artifact spec."""
    m = re.search(spec["regex"], text)
    if not m:
        return [f"artifact path not found in output (regex {spec['regex']!r})"]
    p = Path(m.group(1).strip())
    if not p.is_absolute():
        p = domain_dir / p
    if not p.exists():
        return [f"artifact {p} does not exist"]
    fails = []
    if p.is_dir():
        for name in spec.get("dir_contains", []):
            if not (p / name).exists():
                fails.append(f"dir {p} missing {name}")
        return fails
    size = p.stat().st_size
    if size < spec.get("min_size", 16):
        fails.append(f"artifact {p} too small ({size} bytes)")
    head = p.open("rb").read(16)
    ext = p.suffix.lower()
    want_ext = spec.get("ext")
    if want_ext and ext != want_ext:
        fails.append(f"artifact {p} has extension {ext}, expected {want_ext}")
    if ext in MAGIC and not any(head.startswith(mg) for mg in MAGIC[ext]):
        fails.append(f"artifact {p} bad magic bytes {head[:8]!r} for {ext}")
    if ext == ".mp4" and head[4:8] != b"ftyp":
        fails.append(f"artifact {p} is not a real mp4 (no ftyp)")
    if "pdf_text" in spec:
        out = subprocess.run(["pdftotext", str(p), "-"], capture_output=True, text=True).stdout
        for needle in spec["pdf_text"]:
            if needle.lower() not in out.lower():
                fails.append(f"pdf text of {p} lacks {needle!r}")
    if "contains" in spec:
        body = p.read_text(errors="replace")
        for needle in spec["contains"]:
            if needle.lower() not in body.lower():
                fails.append(f"file {p} lacks {needle!r}")
    if "zip_entries" in spec:
        n = len(zipfile.ZipFile(p).namelist())
        if n != spec["zip_entries"]:
            fails.append(f"zip {p} has {n} entries, expected {spec['zip_entries']}")
    if "duration" in spec:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                             capture_output=True, text=True).stdout.strip()
        try:
            d = float(out)
            lo, hi = spec["duration"]
            if not lo <= d <= hi:
                fails.append(f"media {p} duration {d:.2f}s not in [{lo},{hi}]")
        except ValueError:
            fails.append(f"ffprobe could not read duration of {p}")
    if "image_size" in spec and ext == ".png":
        w, h = struct.unpack(">II", p.open("rb").read(24)[16:24])
        if [w, h] != spec["image_size"]:
            fails.append(f"png {p} is {w}x{h}, expected {spec['image_size']}")
    return fails


def setup_payer(algod_client, cfg):
    REPO = SERVERS.parent
    sys.path.insert(0, str(REPO / "chain"))
    from common import dispenser
    from algosdk import account, transaction, mnemonic
    import warnings
    disp_addr, disp_sk = dispenser()
    payer_sk, payer_addr = account.generate_account()
    sp = algod_client.suggested_params()
    fund_txn = transaction.PaymentTxn(disp_addr, sp, payer_addr, 10_000_000)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        stxn = fund_txn.sign(disp_sk)
    txid = algod_client.send_transaction(stxn)
    transaction.wait_for_confirmation(algod_client, txid, 4)

    musd_id = cfg.get("musd_asset_id", 3456)
    if musd_id:
        sp = algod_client.suggested_params()
        optin_txn = transaction.AssetTransferTxn(payer_addr, sp, payer_addr, 0, musd_id)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            stxn_optin = optin_txn.sign(payer_sk)
        txid = algod_client.send_transaction(stxn_optin)
        transaction.wait_for_confirmation(algod_client, txid, 4)

        server_addr = cfg["accounts"]["server"]["address"]
        server_sk = mnemonic.to_private_key(cfg["accounts"]["server"]["mnemonic"])
        sp = algod_client.suggested_params()
        send_musd = transaction.AssetTransferTxn(server_addr, sp, payer_addr, 50_000_000, musd_id)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            stxn_musd = send_musd.sign(server_sk)
        txid = algod_client.send_transaction(stxn_musd)
        transaction.wait_for_confirmation(algod_client, txid, 4)

    return payer_sk, payer_addr


async def probe_port(domain, port, cases, required_tools, tmp, results, paid=False, payer_sk=None, payer_addr=None):
    domain_dir = SERVERS / domain
    outputs = {}
    url = f"http://127.0.0.1:{port}/sse"
    try:
        if paid:
            import base64
            from ai_economy_sdk.client import paid_mcp_session
            from algosdk import encoding
            from algosdk.v2client import algod

            REPO = SERVERS.parent
            cfg = json.loads((REPO / "chain" / "accounts.json").read_text())
            pricing = json.loads((SERVERS / "pricing.json").read_text())
            domain_pricing = pricing["domains"].get(domain, {})
            algod_client = algod.AlgodClient(cfg["algod_token"], cfg["algod_url"])
            server_addr = cfg["accounts"]["server"]["address"]

            def normalize_address(x):
                if not x:
                    return ""
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

            if not payer_sk or not payer_addr:
                payer_sk, payer_addr = setup_payer(algod_client, cfg)
                print(f"payer {payer_addr}")

            mp_path = Path(os.environ.get("MARKETPLACE_JSON", SERVERS / "marketplace.json"))
            mp = None
            listing = None
            if mp_path.exists():
                try:
                    mp = json.loads(mp_path.read_text())
                    for item in mp.get("listings", []):
                        if item.get("port") == port:
                            listing = item
                            break
                except Exception:
                    pass

            if listing and mp:
                vendor_name = listing["vendor"]
                vendor_addr = cfg["accounts"][vendor_name]["address"]
                listing_asset = listing.get("asset", "ALGO")
                asset_id = mp["assets"].get(listing_asset, 0)
                listing_prices = listing.get("prices", {})
                min_price = pricing.get("minimum", 3000)
                listing_default = max(min_price, round(pricing["default"] * listing.get("multiplier", 1.0)))
            else:
                vendor_name = "server"
                vendor_addr = server_addr
                listing_asset = "ALGO"
                asset_id = 0
                listing_prices = domain_pricing
                listing_default = pricing.get("default", 1000)

            session_cm = paid_mcp_session(
                url,
                payer_sk,
                cfg["network"],
                algod_url=cfg["algod_url"],
                algod_token=cfg["algod_token"],
            )
        else:
            from mcp.client.session import ClientSession
            from mcp.client.sse import sse_client
            import contextlib

            @contextlib.asynccontextmanager
            async def _plain_session():
                async with sse_client(url, timeout=10, sse_read_timeout=900) as (r, w):
                    async with ClientSession(r, w) as s:
                        await s.initialize()
                        s._raw_write_stream = w
                        yield s

            session_cm = _plain_session()

        async with session_cm as s:
            names = {t.name for t in (await s.list_tools()).tools}
            missing = sorted(set(required_tools) - names)
            results.append({"port": port, "case": "list_tools", "ok": not missing,
                            "why": f"missing tools {missing}" if missing else f"{len(names)} tools"})
            for case in cases:
                args = subst(case.get("args", {}), port, tmp)
                why = []
                info = None
                is_error = False
                if paid:
                    if listing_asset == "ALGO":
                        bal_before = algod_client.account_info(vendor_addr)["amount"]
                    else:
                        acc_info = algod_client.account_info(vendor_addr)
                        bal_before = 0
                        for a in acc_info.get("assets", []):
                            if a.get("asset-id") == asset_id:
                                bal_before = a.get("amount", 0)
                                break
                    start_round = algod_client.status()["last-round"]

                try:
                    w = getattr(s, "_raw_write_stream", None)

                    async def _call_monitored():
                        task = asyncio.create_task(s.call_tool(case["tool"], args))
                        while not task.done():
                            if w is not None and hasattr(w, "statistics") and w.statistics().open_receive_streams == 0:
                                task.cancel()
                                raise RuntimeError("402 Payment Required: post_writer closed")
                            await asyncio.sleep(0.05)
                        return await task

                    res = await asyncio.wait_for(_call_monitored(), timeout=case.get("timeout", 120))
                    text = "\n".join(getattr(c, "text", "") or "" for c in res.content)
                    is_error = getattr(res, "isError", False)
                    if res.isError and not case.get("allow_error") and not case.get("must_error"):
                        why.append("tool returned isError=True")
                    if case.get("must_error") and not res.isError:
                        why.append("expected isError=True (tool must raise ToolError) but got a normal result")
                except Exception as e:  # noqa: BLE001
                    text = f"<exception {type(e).__name__}: {e}>"
                    is_error = True
                    why.append(text)

                if paid:
                    if listing_asset == "ALGO":
                        bal_after = algod_client.account_info(vendor_addr)["amount"]
                    else:
                        acc_info = algod_client.account_info(vendor_addr)
                        bal_after = 0
                        for a in acc_info.get("assets", []):
                            if a.get("asset-id") == asset_id:
                                bal_after = a.get("amount", 0)
                                break
                    delta = bal_after - bal_before
                    current_round = algod_client.status()["last-round"]
                    if current_round <= start_round:
                        for _ in range(10):
                            await asyncio.sleep(0.1)
                            current_round = algod_client.status()["last-round"]
                            if current_round > start_round:
                                break

                    found_txn = None
                    pay_amt = None
                    pay_grp = None
                    pay_round = None
                    for r in range(start_round + 1, current_round + 1):
                        blk = algod_client.block_info(r)
                        txns = blk.get("block", {}).get("txns", [])
                        for t in txns:
                            tb = t.get("txn", {})
                            ttype = tb.get("type")
                            snd = normalize_address(tb.get("snd"))
                            if listing_asset == "ALGO" and ttype == "pay":
                                rcv = normalize_address(tb.get("rcv"))
                                if snd == payer_addr and rcv == vendor_addr:
                                    found_txn = tb
                                    pay_amt = tb.get("amt", 0)
                                    pay_grp = tb.get("grp")
                                    pay_round = r
                                    break
                            elif listing_asset == "mUSD" and ttype == "axfer":
                                arcv = normalize_address(tb.get("arcv"))
                                xaid = tb.get("xaid")
                                if snd == payer_addr and arcv == vendor_addr and xaid == asset_id:
                                    found_txn = tb
                                    pay_amt = tb.get("aamt", 0)
                                    pay_grp = tb.get("grp")
                                    pay_round = r
                                    break
                        if found_txn is not None:
                            break

                    expected_price = listing_prices.get(case["tool"], listing_default)
                    if os.environ.get("PROBE_PRICE_OVERRIDE"):
                        try:
                            expected_price = int(os.environ["PROBE_PRICE_OVERRIDE"])
                        except ValueError:
                            pass

                    if is_error:
                        if found_txn is not None:
                            why.append(f"tool error but on-chain payment found: {pay_amt}")
                            info = f"paid={pay_amt} (unexpected payment for tool error)"
                        else:
                            info = "paid=0 (tool error, not charged)"
                    else:
                        if found_txn is None:
                            why.append("no on-chain payment found")
                            info = f"net={delta}"
                        else:
                            if pay_amt != expected_price:
                                why.append(f"amount {pay_amt} != expected {expected_price}")

                            vendor_fees = 0
                            fee_payer_ok = False
                            if pay_grp is not None:
                                blk = algod_client.block_info(pay_round)
                                txns = blk.get("block", {}).get("txns", [])
                                grp_txns = [t for t in txns if t.get("txn", {}).get("grp") == pay_grp]
                                vendor_fees = sum(
                                    t.get("txn", {}).get("fee", 0)
                                    for t in grp_txns
                                    if normalize_address(t.get("txn", {}).get("snd")) == vendor_addr
                                )
                                fee_payer_ok = any(
                                    normalize_address(t.get("txn", {}).get("snd")) == vendor_addr and t.get("txn", {}).get("fee", 0) > 0
                                    for t in grp_txns
                                )
                            if not fee_payer_ok:
                                why.append(f"fee payer is not vendor {vendor_name} ({vendor_addr})")

                            other_delta = 0
                            for r in range(start_round + 1, current_round + 1):
                                blk = algod_client.block_info(r)
                                for t in blk.get("block", {}).get("txns", []):
                                    tb = t.get("txn", {})
                                    if tb.get("grp") == pay_grp:
                                        continue
                                    snd = normalize_address(tb.get("snd"))
                                    if listing_asset == "ALGO" and tb.get("type") == "pay":
                                        rcv = normalize_address(tb.get("rcv"))
                                        if rcv == vendor_addr:
                                            other_delta += tb.get("amt", 0)
                                        if snd == vendor_addr:
                                            other_delta -= tb.get("amt", 0)
                                            other_delta -= tb.get("fee", 0)
                                    elif listing_asset == "mUSD" and tb.get("type") == "axfer" and tb.get("xaid") == asset_id:
                                        arcv = normalize_address(tb.get("arcv"))
                                        if arcv == vendor_addr:
                                            other_delta += tb.get("aamt", 0)
                                        if snd == vendor_addr:
                                            other_delta -= tb.get("aamt", 0)

                            if listing_asset == "ALGO":
                                expected_delta = pay_amt - vendor_fees
                            else:
                                expected_delta = pay_amt

                            if delta != expected_delta and (delta - other_delta) != expected_delta:
                                why.append(f"vendor {listing_asset} balance delta {delta} != net {expected_delta}")

                            effective_delta = delta if delta == expected_delta else (delta - other_delta)
                            info = f"paid={pay_amt} {listing_asset} to={vendor_name} fee={vendor_fees} net={effective_delta}"

                outputs[case["id"]] = text
                for rx in case.get("expect", []):
                    if not re.search(rx, text, re.S):
                        why.append(f"expected /{rx}/")
                for rx in case.get("reject", []):
                    if re.search(rx, text, re.S):
                        why.append(f"rejected /{rx}/ matched")
                for a in case.get("artifacts", []):
                    why += check_artifact(subst(a, port, tmp), text, domain_dir)
                ref = case.get("must_differ_from")
                if ref and outputs.get(ref) == text:
                    why.append(f"output identical to case {ref} (looks hard-coded)")

                if paid and info is not None:
                    why_str = f"{'; '.join(why)}; {info}" if why else info
                else:
                    why_str = "; ".join(why)

                results.append({"port": port, "case": case["id"], "ok": not why, "why": why_str,
                                "output": text[:400]})
    except Exception as e:  # noqa: BLE001
        results.append({"port": port, "case": "connect", "ok": False, "why": f"{type(e).__name__}: {e}"})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("domain")
    ap.add_argument("--port", type=int)
    ap.add_argument("--json")
    ap.add_argument("--paid", action="store_true", help="Connect with paid MCP session and verify on-chain payment")
    a = ap.parse_args()
    topo = json.loads((SERVERS / "topology.json").read_text())[a.domain]
    matrix = json.loads((SERVERS / "tools" / "test_matrix.json").read_text())[a.domain]
    ports = [a.port] if a.port else topo["proxy_ports"]
    tmp = SERVERS / "tests" / "outputs" / "probe" / a.domain
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True, exist_ok=True)
    results = []
    payer_sk, payer_addr = None, None
    if a.paid:
        REPO = SERVERS.parent
        cfg = json.loads((REPO / "chain" / "accounts.json").read_text())
        sys.path.insert(0, str(REPO / "chain"))
        from common import algod_client as get_algod_client
        _algod = get_algod_client()
        payer_sk, payer_addr = setup_payer(_algod, cfg)
        print(f"payer {payer_addr}")

    for p in ports:
        asyncio.run(probe_port(a.domain, p, matrix["cases"], matrix["tools"], tmp, results, paid=a.paid, payer_sk=payer_sk, payer_addr=payer_addr))
    # cross-port uniqueness of artifacts (e.g. proxies must not overwrite each other's files)
    for case in matrix["cases"]:
        if case.get("unique_across_ports") and len(ports) > 1:
            outs = [r["output"] for r in results if r["case"] == case["id"]]
            if len(set(outs)) != len(outs):
                results.append({"port": "*", "case": case["id"] + ":unique", "ok": False,
                                "why": "different proxies returned identical output paths (they overwrite each other)"})
    width = max(len(r["case"]) for r in results)
    for r in results:
        print(f"{'PASS' if r['ok'] else 'FAIL'}  {str(r['port']):5}  {r['case']:{width}}  {r['why']}")
    npass = sum(r["ok"] for r in results)
    print(f"\nSUMMARY {a.domain}: {npass}/{len(results)} checks passed")
    if a.json:
        Path(a.json).write_text(json.dumps(results, indent=2))
    sys.exit(0 if npass == len(results) else 1)


if __name__ == "__main__":
    main()
