import os
import torch
import pytest
from app.utils.hardware import (
    get_cpu_model_name,
    has_avx512,
    verify_dgpu_isolated,
    get_system_hardware_profile
)

def test_dgpu_isolation():
    """Verify that NVIDIA discrete GPU is strictly isolated and unreachable."""
    assert os.environ.get("CUDA_VISIBLE_DEVICES") == ""
    assert not torch.cuda.is_available(), "CUDA must not be available!"
    assert verify_dgpu_isolated() is True

def test_cpu_model_detection():
    """Verify CPU model name string is non-empty."""
    model = get_cpu_model_name()
    assert isinstance(model, str)
    assert len(model) > 0
    print(f"Detected CPU: {model}")

def test_avx512_detection():
    """Verify AVX-512 detection returns boolean without crashing."""
    result = has_avx512()
    assert isinstance(result, bool)

def test_hardware_profile_structure():
    """Verify system hardware profile schema."""
    profile = get_system_hardware_profile()
    assert profile["device"] == "cpu"
    assert profile["dgpu_isolated"] is True
    assert profile["torch_threads"] >= 1
    assert profile["memory_total_gb"] > 0
    assert profile["status"] == "production_ready_cpu_optimized"
