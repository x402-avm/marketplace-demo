import hashlib
import json
from pathlib import Path
import sys
import pytest

REPO_DIR = Path(__file__).resolve().parents[2]
CHAIN_DIR = REPO_DIR / "chain"
if str(CHAIN_DIR) not in sys.path:
    sys.path.insert(0, str(CHAIN_DIR))

import bootstrap
import common
import gen_listings

ACCOUNTS_FILE = CHAIN_DIR / "accounts.json"
TOPOLOGY_FILE = REPO_DIR / "servers" / "topology.json"
PRICING_FILE = REPO_DIR / "servers" / "pricing.json"
MARKETPLACE_FILE = REPO_DIR / "servers" / "marketplace.json"

if not ACCOUNTS_FILE.exists():
    pytestmark = pytest.mark.skip(reason="chain/accounts.json not present (requires bootstrap.py on LocalNet)")

VENDORS = ["vendorA", "vendorB", "vendorC", "vendorD"]
EXPECTED_MULTIPLIERS = {
    "vendorA": 1.0,
    "vendorB": 0.8,
    "vendorC": 1.25,
    "vendorD": 1.5,
}


def test_gen_listings_total_count():
    data = gen_listings.generate_marketplace_data()
    assert len(data["listings"]) == 64, f"Expected 64 listings, got {len(data['listings'])}"


def test_gen_listings_covers_all_topology():
    data = gen_listings.generate_marketplace_data()
    topology = json.loads(TOPOLOGY_FILE.read_text(encoding="utf-8"))

    seen_pairs = set()
    for item in data["listings"]:
        pair = (item["domain"], item["proxy_index"])
        assert pair not in seen_pairs, f"Duplicate listing for {pair}"
        seen_pairs.add(pair)

        # Verify port matches topology
        expected_ports = topology[item["domain"]]["proxy_ports"]
        assert item["port"] == expected_ports[item["proxy_index"] - 1]

    # Every proxy in topology must appear
    expected_pairs = {
        (domain, idx)
        for domain, d in topology.items()
        for idx in range(1, len(d["proxy_ports"]) + 1)
    }
    assert seen_pairs == expected_pairs


def test_gen_listings_vendor_rule():
    data = gen_listings.generate_marketplace_data()
    for item in data["listings"]:
        idx = item["proxy_index"]
        expected_vendor = VENDORS[(idx - 1) % 4]
        assert item["vendor"] == expected_vendor, f"Listing {item['id']} has vendor {item['vendor']}, expected {expected_vendor}"
        assert item["multiplier"] == EXPECTED_MULTIPLIERS[expected_vendor]


def test_gen_listings_asset_rule():
    data = gen_listings.generate_marketplace_data()
    for item in data["listings"]:
        if item["vendor"] == "vendorB":
            assert item["asset"] == "mUSD", f"vendorB listing {item['id']} should use mUSD"
        else:
            assert item["asset"] == "ALGO", f"Non-vendorB listing {item['id']} should use ALGO"


def test_gen_listings_no_price_below_minimum():
    pricing = json.loads(PRICING_FILE.read_text(encoding="utf-8"))
    min_price = int(pricing.get("minimum", pricing.get("default", 3000)))
    data = gen_listings.generate_marketplace_data()

    for item in data["listings"]:
        prices = item.get("prices", {})
        assert len(prices) > 0, f"Listing {item['id']} has empty prices dict"
        for tool, p in prices.items():
            assert p >= min_price, f"Listing {item['id']} tool {tool} price {p} is below minimum {min_price}"


def test_gen_listings_deterministic():
    data1 = gen_listings.generate_marketplace_data()
    text1 = json.dumps(data1, indent=2) + "\n"
    h1 = hashlib.sha256(text1.encode("utf-8")).hexdigest()

    data2 = gen_listings.generate_marketplace_data()
    text2 = json.dumps(data2, indent=2) + "\n"
    h2 = hashlib.sha256(text2.encode("utf-8")).hexdigest()

    assert text1 == text2
    assert h1 == h2


def test_gen_listings_sorted_by_domain_and_proxy_index():
    data = gen_listings.generate_marketplace_data()
    keys = [(item["domain"], item["proxy_index"]) for item in data["listings"]]
    assert keys == sorted(keys), "Listings are not sorted by domain then proxy_index"


def test_marketplace_json_contains_no_secrets():
    content = MARKETPLACE_FILE.read_text(encoding="utf-8")
    accounts_data = json.loads(ACCOUNTS_FILE.read_text(encoding="utf-8"))

    # Assert no account mnemonic appears in marketplace.json
    for role, acc in accounts_data.get("accounts", {}).items():
        mn = acc.get("mnemonic", "")
        if mn:
            words = mn.split()
            # check the whole phrase and 4-word slices
            assert mn not in content, f"Secret mnemonic for {role} leaked in marketplace.json!"
            for i in range(len(words) - 3):
                phrase = " ".join(words[i:i+4])
                assert phrase not in content, f"Secret mnemonic fragment for {role} leaked in marketplace.json!"


# --- LIVE LOCALNET TESTS ---

@pytest.mark.localnet
def test_localnet_vendors_exist_and_funded():
    algod = common.algod_client()
    accounts_data = common.load_accounts()

    for v in VENDORS:
        assert v in accounts_data["accounts"], f"Missing {v} in accounts.json"
        addr = accounts_data["accounts"][v]["address"]
        info = algod.account_info(addr)
        bal_algo = info["amount"] / 1_000_000
        assert bal_algo >= 50.0, f"Vendor {v} balance {bal_algo} ALGO < 50 ALGO"


@pytest.mark.localnet
def test_localnet_vendors_opted_into_assets():
    algod = common.algod_client()
    accounts_data = common.load_accounts()
    musd_id = accounts_data["musd_asset_id"]
    sub_id = accounts_data["subscription_asset_id"]

    for v in VENDORS:
        addr = accounts_data["accounts"][v]["address"]
        info = algod.account_info(addr)
        holding_ids = {a["asset-id"] for a in info.get("assets", [])}
        assert musd_id in holding_ids, f"Vendor {v} not opted into mUSD (asset {musd_id})"
        assert sub_id in holding_ids, f"Vendor {v} not opted into AI-SUB (asset {sub_id})"


@pytest.mark.localnet
def test_localnet_musd_asset_parameters():
    algod = common.algod_client()
    accounts_data = common.load_accounts()
    musd_id = accounts_data["musd_asset_id"]
    server_addr = accounts_data["accounts"]["server"]["address"]

    info = algod.asset_info(musd_id)
    params = info["params"]
    assert params["name"] == "Marketplace USD"
    assert params["unit-name"] == "mUSD"
    assert params["total"] == 10**15
    assert params["decimals"] == 6
    assert params["default-frozen"] is False
    assert params["manager"] == server_addr
    assert params["reserve"] == server_addr
    assert params.get("freeze") is None or params.get("freeze") == ""
    assert params.get("clawback") is None or params.get("clawback") == ""


@pytest.mark.localnet
def test_localnet_clients_hold_musd():
    algod = common.algod_client()
    accounts_data = common.load_accounts()
    musd_id = accounts_data["musd_asset_id"]

    for c in ["client1", "client2"]:
        addr = accounts_data["accounts"][c]["address"]
        info = algod.account_info(addr)
        musd_bal = next((a["amount"] for a in info.get("assets", []) if a["asset-id"] == musd_id), 0)
        assert musd_bal >= 100 * 10**6, f"Client {c} holds {musd_bal / 1e6} mUSD < 100 mUSD"


@pytest.mark.localnet
def test_localnet_bootstrap_idempotent_zero_transactions():
    algod = common.algod_client()
    round_before = algod.status()["last-round"]

    # Run bootstrap
    bootstrap.main()

    round_after = algod.status()["last-round"]
    assert round_before == round_after, (
        f"Bootstrap submitted transactions on second run! Round before: {round_before}, after: {round_after}"
    )
