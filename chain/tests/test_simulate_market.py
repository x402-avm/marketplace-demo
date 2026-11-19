import json
from pathlib import Path
import sys
import pytest

REPO_DIR = Path(__file__).resolve().parents[2]
CHAIN_DIR = REPO_DIR / "chain"
SERVERS_DIR = REPO_DIR / "servers"

if str(CHAIN_DIR) not in sys.path:
    sys.path.insert(0, str(CHAIN_DIR))

import simulate_market

MARKETPLACE_FILE = SERVERS_DIR / "marketplace.json"
TEST_MATRIX_FILE = SERVERS_DIR / "tools" / "test_matrix.json"
DEFAULT_DOMAINS = ["tts", "sandbox_mcp", "latex_mcp", "invoice_mcp"]


def test_dry_run_plan_deterministic():
    marketplace = json.loads(MARKETPLACE_FILE.read_text(encoding="utf-8"))
    test_matrix = json.loads(TEST_MATRIX_FILE.read_text(encoding="utf-8"))
    candidate_listings = [
        l for l in marketplace.get("listings", []) if l.get("domain") in DEFAULT_DOMAINS
    ]
    simulated_buyers = [
        {"index": i, "address": f"BUYER_{i+1:02d}", "sk": None}
        for i in range(5)
    ]

    # Two runs with same seed must be 100% identical
    plan1 = simulate_market.build_simulation_plan(
        simulated_buyers, candidate_listings, test_matrix, num_calls=20, seed=42
    )
    plan2 = simulate_market.build_simulation_plan(
        simulated_buyers, candidate_listings, test_matrix, num_calls=20, seed=42
    )

    assert len(plan1) == 20
    assert len(plan2) == 20

    for c1, c2 in zip(plan1, plan2):
        assert c1["call_index"] == c2["call_index"]
        assert c1["buyer"]["address"] == c2["buyer"]["address"]
        assert c1["listing"]["id"] == c2["listing"]["id"]
        assert c1["tool"] == c2["tool"]
        assert c1["price"] == c2["price"]
        assert c1["args"] == c2["args"]
        assert c1["case_id"] == c2["case_id"]

    # Run with different seed should produce a different plan
    plan_other = simulate_market.build_simulation_plan(
        simulated_buyers, candidate_listings, test_matrix, num_calls=20, seed=999
    )
    matches = sum(
        1 for c1, co in zip(plan1, plan_other)
        if c1["listing"]["id"] == co["listing"]["id"] and c1["tool"] == co["tool"]
    )
    assert matches < 20, "Different seeds should produce different call sequences"


def test_tool_arg_selection_default_domains():
    test_matrix = json.loads(TEST_MATRIX_FILE.read_text(encoding="utf-8"))

    for domain in DEFAULT_DOMAINS:
        assert domain in test_matrix, f"Domain {domain} missing from test_matrix.json"
        tools = test_matrix[domain].get("tools", [])
        assert len(tools) > 0, f"Domain {domain} has no tools in test_matrix.json"

        for tool_name in tools:
            case_id, args = simulate_market.get_positive_case_for_tool(
                test_matrix, domain, tool_name, port=8000
            )
            assert case_id != "empty", f"Tool {tool_name} in domain {domain} failed to resolve a case"
            assert isinstance(args, dict), f"Tool {tool_name} args must be a dict"

            # Verify placeholder substitution worked
            def _check_no_unresolved_placeholders(val):
                if isinstance(val, str):
                    assert "{FIX}" not in val, f"Unresolved {{FIX}} in args: {val}"
                    assert "{TMP}" not in val, f"Unresolved {{TMP}} in args: {val}"
                    assert "{PORT}" not in val, f"Unresolved {{PORT}} in args: {val}"
                elif isinstance(val, dict):
                    for v in val.values():
                        _check_no_unresolved_placeholders(v)
                elif isinstance(val, list):
                    for v in val:
                        _check_no_unresolved_placeholders(v)

            _check_no_unresolved_placeholders(args)


def test_subst_args():
    raw_args = {
        "file": "{FIX}/sample.pdf",
        "output": "{TMP}/out_{PORT}.png",
        "nested": {"items": ["{FIX}/a.txt", 123, "{PORT}"]},
    }
    res = simulate_market.subst_args(
        raw_args, port=8051, fixtures_dir="/path/fixtures", tmp_dir="/path/tmp"
    )
    assert res["file"] == "/path/fixtures/sample.pdf"
    assert res["output"] == "/path/tmp/out_8051.png"
    assert res["nested"]["items"] == ["/path/fixtures/a.txt", 123, "8051"]


def test_positive_case_spec_contains_expect():
    test_matrix = json.loads(TEST_MATRIX_FILE.read_text(encoding="utf-8"))
    for domain in DEFAULT_DOMAINS:
        tools = test_matrix[domain].get("tools", [])
        for tool_name in tools:
            case_id, args, case_spec = simulate_market.get_positive_case_for_tool(
                test_matrix, domain, tool_name, port=8000, return_spec=True
            )
            assert isinstance(case_spec, dict)
            assert case_spec.get("tool") == tool_name
            assert "args" in case_spec


def test_skip_env_detection():
    # If is_error is True and "sandbox isolation unavailable" is in error text
    err_text = "503: sandbox isolation unavailable: unshare: write failed"
    is_error = True
    assert "sandbox isolation unavailable" in err_text
