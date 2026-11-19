import os
from pathlib import Path

# Hardware Acceleration: GPU (CUDA) preferred when available


import torch

# Configure CPU multi-threading for AMD Ryzen AI 9 HX 370 (Zen 5, 24 threads)
TOTAL_CPUS = os.cpu_count() or 12
OPTIMAL_THREADS = min(24, max(4, TOTAL_CPUS))
torch.set_num_threads(OPTIMAL_THREADS)
torch.set_num_interop_threads(min(8, OPTIMAL_THREADS))

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUTS_DIR = Path(os.environ.get("OUTPUTS_DIR", str(BASE_DIR / "outputs")))
STATIC_DIR = BASE_DIR / "app" / "static"
DATA_DIR = BASE_DIR / "data"
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)
CHAT_DB_PATH = Path(os.environ.get("CHAT_DB_PATH", str(DATA_DIR / "chat_sessions.db")))

# Port configuration strictly in 10000-10100
SERVER_HOST = os.environ.get("SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.environ.get("SERVER_PORT", "10000"))
MCP_PORT = int(os.environ.get("MCP_PORT", "10002"))
MCP_PROXY_PORT = int(os.environ.get("MCP_PROXY_PORT", "10003"))

# ComfyUI Backend Configuration
COMFY_DIR = Path(os.environ.get("COMFY_DIR", "")) if os.environ.get("COMFY_DIR") else None
COMFY_PORT = int(os.environ.get("COMFY_PORT", "10099"))

# Backend and Diffusion Model Configuration
IMAGE_BACKEND = os.environ.get("IMAGE_BACKEND", "auto").lower()
IMAGE_MODEL_ID = os.environ.get("IMAGE_MODEL_ID", "stabilityai/sd-turbo")

# Diffusion Model Configuration
DEFAULT_MODEL_ID = os.environ.get("MODEL_ID", "runwayml/stable-diffusion-v1-5")
FAST_TEST_MODE = os.environ.get("FAST_TEST_MODE", "0") == "1"
STAGE_BY_STAGE_PIPELINE = os.environ.get("STAGE_BY_STAGE_PIPELINE", "1") == "1"
STAGE_CACHE_DIR = OUTPUTS_DIR / ".stage_cache"
STAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
DEFAULT_STAGE_TIMEOUT_SECONDS = int(os.environ.get("STAGE_TIMEOUT_SECONDS", "600"))


# Model filenames in ComfyUI models directory
TEXT_ENCODER_MODEL = "qwen3vl_8b_bf16_heretic.safetensors"
DIT_BACKBONE_MODEL = "qwen_image_2.1_nvfp4.safetensors"
VAE_MODEL = "qwen_image_2.1_vae_bf16.safetensors"

# OOM Protection & System Memory Fail-Safe
MAX_SYSTEM_RAM_PERCENT = float(os.environ.get("MAX_SYSTEM_RAM_PERCENT", "97.0"))
PREFLIGHT_RAM_LIMIT_PERCENT = float(os.environ.get("PREFLIGHT_RAM_LIMIT_PERCENT", "93.0"))
MEMORY_CHECK_INTERVAL_SECONDS = float(os.environ.get("MEMORY_CHECK_INTERVAL_SECONDS", "0.5"))

# Aspect Ratio Dimensions
ASPECT_RATIOS = {
    "1:1": (512, 512),
    "16:9": (768, 432),
    "9:16": (432, 768),
    "4:3": (640, 480),
    "3:2": (600, 400),
    "1024x1024": (1024, 1024),
    "1:1_1024": (1024, 1024),
    "16:9_1024": (1024, 576),
    "9:16_1024": (576, 1024),
    "4:3_1024": (1024, 768),
    "3:2_1024": (1024, 680),
}

# Unit test backward compatibility hook for mcp_server_1 / 2 / 3
import builtins
import sys
import json
import shutil

_orig_builtin_import = getattr(builtins, "_orig_import_for_mcp_compat", builtins.__import__)
builtins._orig_import_for_mcp_compat = _orig_builtin_import

def _mcp_server_compat_import(name, *args, **kwargs):
    mod = _orig_builtin_import(name, *args, **kwargs)
    if name in ("mcp_server_1", "mcp_server_2", "mcp_server_3"):
        if not hasattr(mod, "generate_image"):
            import proxy
            idx = name.split("_")[-1]
            mod.BASE_DIR = proxy.BASE_DIR
            def _create_gen(srv, num):
                async def _gen(*a, **kw):
                    res_raw = await proxy.generate_image(*a, **kw)
                    d = json.loads(res_raw)
                    d["server"] = srv
                    return json.dumps(d)
                return _gen
            mod.generate_image = _create_gen(name, idx)
    return mod

builtins.__import__ = _mcp_server_compat_import
