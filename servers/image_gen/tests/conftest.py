import os
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Strictly enforce CPU-only isolation before anything else
os.environ["CUDA_VISIBLE_DEVICES"] = ""
os.environ["FAST_TEST_MODE"] = "1"
os.environ["SERVER_PORT"] = "10000"
os.environ["MCP_PORT"] = "10002"

import tempfile
_TEST_TMP_DIR = Path(tempfile.gettempdir()) / "pytest_image_gen_outputs"
_TEST_TMP_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("OUTPUTS_DIR", str(_TEST_TMP_DIR))

import pytest

@pytest.fixture(autouse=True)
def enforce_cpu_environment():
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    os.environ["FAST_TEST_MODE"] = "1"
    yield

@pytest.fixture(autouse=True)
def configure_test_output_dir(tmp_path, monkeypatch):
    test_outputs = tmp_path / "outputs"
    test_outputs.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("OUTPUTS_DIR", str(test_outputs))
    import app.config as app_config
    monkeypatch.setattr(app_config, "OUTPUTS_DIR", test_outputs)
    stage_cache = test_outputs / ".stage_cache"
    stage_cache.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(app_config, "STAGE_CACHE_DIR", stage_cache)
    yield
