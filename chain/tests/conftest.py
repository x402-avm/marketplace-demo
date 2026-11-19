import os
import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "localnet: mark test to run only when LOCALNET=1"
    )


def pytest_collection_modifyitems(config, items):
    """Tests marked `localnet` need a running AlgoKit LocalNet; skip them unless LOCALNET=1."""
    if os.environ.get("LOCALNET") == "1":
        return
    skip = pytest.mark.skip(reason="set LOCALNET=1 with algokit localnet running")
    for it in items:
        if "localnet" in it.keywords:
            it.add_marker(skip)
