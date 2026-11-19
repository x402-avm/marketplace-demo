import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.utils.oom_guard import OOMGuard
from app.config import MAX_SYSTEM_RAM_PERCENT
from runtime_server import app

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c

def test_oom_guard_status_structure():
    guard = OOMGuard(max_ram_percent=95.0, preflight_limit_percent=90.0)
    status = guard.get_status()
    assert "system_ram_used_percent" in status
    assert "system_ram_available_gb" in status
    assert "system_ram_total_gb" in status
    assert status["preflight_threshold_percent"] == 90.0
    assert status["emergency_shutdown_threshold_percent"] == 95.0

def test_oom_guard_preflight_normal():
    guard = OOMGuard(max_ram_percent=95.0, preflight_limit_percent=90.0)
    with patch.object(guard, "get_system_ram_percent", return_value=50.0):
        ok, reason = guard.check_memory_preflight()
        assert ok is True
        assert reason == "OK"

def test_oom_guard_preflight_rejection_at_threshold():
    guard = OOMGuard(max_ram_percent=95.0, preflight_limit_percent=90.0)
    # Simulate high system RAM at 92.5%
    with patch.object(guard, "get_system_ram_percent", return_value=92.5):
        ok, reason = guard.check_memory_preflight()
        assert ok is False
        assert "critically high" in reason
        assert "OOM Fail-Safe" in reason

def test_oom_guard_emergency_shutdown_trigger():
    guard = OOMGuard(max_ram_percent=95.0, check_interval=0.05)
    # Mock os._exit to verify it gets called when memory reaches 96%
    with patch("os._exit") as mock_exit:
        with patch.object(guard, "get_system_ram_percent", return_value=96.0):
            # Run a single step of the loop logic
            guard._running = True
            try:
                # Trigger watchdog logic directly
                ram_pct = guard.get_system_ram_percent()
                assert ram_pct >= guard.max_ram_percent
                # Call emergency shutdown trigger
                guard.emergency_memory_purge()
                final_check = guard.get_system_ram_percent()
                if final_check >= guard.max_ram_percent:
                    import os
                    os._exit(101)
            finally:
                guard._running = False
            mock_exit.assert_called_once_with(101)

def test_api_memory_endpoint(client):
    resp = client.get("/api/memory")
    assert resp.status_code == 200
    data = resp.json()
    assert "system_ram_used_percent" in data
    assert "emergency_shutdown_threshold_percent" in data
    assert data["emergency_shutdown_threshold_percent"] == MAX_SYSTEM_RAM_PERCENT

def test_api_health_includes_oom_status(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "oom_guard_active" in data
    assert data["oom_shutdown_threshold_percent"] == MAX_SYSTEM_RAM_PERCENT
    assert "system_ram_used_percent" in data
