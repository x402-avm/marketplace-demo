import os
import pytest
import subprocess

# Enforce environment variable isolation
os.environ["CUDA_VISIBLE_DEVICES"] = ""

import torch
from app.utils.hardware import (
    get_cpu_model_name,
    has_avx512,
    verify_dgpu_isolated,
    get_system_hardware_profile
)
from app.config import OPTIMAL_THREADS

def test_cuda_is_disabled():
    """Verify that PyTorch cannot detect or allocate on CUDA."""
    assert not torch.cuda.is_available(), "CUDA must NOT be available!"
    assert torch.cuda.device_count() == 0, "CUDA device count must be 0!"

def test_cuda_visible_devices_env():
    """Verify that CUDA_VISIBLE_DEVICES is set to empty string."""
    assert os.environ.get("CUDA_VISIBLE_DEVICES") == "", "CUDA_VISIBLE_DEVICES must be explicitly empty."

def test_hardware_isolation_function():
    """Verify verify_dgpu_isolated() reports True."""
    assert verify_dgpu_isolated() is True, "Hardware utility must verify dGPU is isolated."

def test_zero_cuda_vram_allocation():
    """Perform CPU tensor computation and verify discrete GPU VRAM is completely untouched."""
    # Allocate a large tensor on CPU
    x = torch.randn(1000, 1000, dtype=torch.float32)
    y = torch.matmul(x, x)
    assert y.shape == (1000, 1000)
    assert y.device.type == "cpu"
    
    # Query nvidia-smi to ensure this PID is not in nvidia-smi compute processes
    try:
        current_pid = os.getpid()
        result = subprocess.run(
            ["nvidia-smi", "--query-compute-apps=pid,process_name,used_memory", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            pids = [int(line.split(",")[0].strip()) for line in lines if line.strip() and line.split(",")[0].strip().isdigit()]
            assert current_pid not in pids, f"Current PID {current_pid} found running on discrete GPU!"
    except FileNotFoundError:
        pass  # nvidia-smi not available

def test_hardware_profile_structure():
    """Verify system telemetry profile returns complete and accurate hardware facts."""
    profile = get_system_hardware_profile()
    assert "cpu_model" in profile
    assert "cpu_cores_logical" in profile
    assert profile["cpu_cores_logical"] >= 4
    assert profile["torch_threads"] >= 4
    assert profile["device"] == "cpu"
    assert profile["dgpu_isolated"] is True
    assert "AMD" in profile["igpu_description"]
    assert profile["status"] == "production_ready_cpu_optimized"

def test_cpu_threads_configured():
    """Verify PyTorch threads match optimal Zen 5 configuration."""
    assert torch.get_num_threads() == OPTIMAL_THREADS
    assert torch.get_num_threads() >= 4
