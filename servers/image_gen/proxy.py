import os
import sys
import json
import shutil
from pathlib import Path
import httpx
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.paths import safe_path, PathNotAllowed


from app.agents import (
    PromptOptimizerAgent,
    QualityAssuranceAgent
)
from app.utils.hardware import get_system_hardware_profile
from app.utils.image_utils import load_image_from_path_or_b64

RUNTIME_URL = os.environ.get("RUNTIME_URL", "http://127.0.0.1:10000")
BASE_DIR = Path(__file__).resolve().parent

mcp = FastMCP("Gemini Nano Image Gen MCP Server")

local_optimizer = None
local_qa = None

def get_optimizer():
    global local_optimizer
    if local_optimizer is None:
        local_optimizer = PromptOptimizerAgent()
    return local_optimizer

def get_qa():
    global local_qa
    if local_qa is None:
        local_qa = QualityAssuranceAgent()
    return local_qa

@mcp.tool()
async def generate_image(
    prompt: str,
    style: str = "photorealistic",
    negative_prompt: str = "",
    aspect_ratio: str = "1:1",
    steps: int = 15,
    guidance_scale: float = 7.5,
    seed: int = -1,
    auto_optimize: bool = True
) -> str:
    """Generate image via Gemini Nano runtime engine with multi-agent pipeline."""
    payload = {
        "prompt": prompt,
        "style": style,
        "negative_prompt": negative_prompt,
        "aspect_ratio": aspect_ratio,
        "steps": steps,
        "guidance_scale": guidance_scale,
        "seed": None if seed < 0 else seed,
        "auto_optimize": auto_optimize,
        "run_qa": True
    }
    
    try:
        async with httpx.AsyncClient(timeout=600.0) as client:
            resp = await client.post(f"{RUNTIME_URL}/api/generate", json=payload)
    except Exception as e:
        raise ToolError(f"image runtime unavailable: {e}")

    if resp.status_code != 200:
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        raise ToolError(str(detail))

    try:
        data = resp.json()
    except Exception as e:
        raise ToolError(f"invalid JSON response from runtime: {e}")

    if data.get("status") == "error" or data.get("success") is False:
        detail = data.get("detail") or data.get("message") or data.get("error") or "image generation failed"
        raise ToolError(str(detail))

    pid = os.getpid()
    return json.dumps({
        "status": "success",
        "file_path": data.get("file_path"),
        "filename": data.get("filename"),
        "backend": data.get("backend"),
        "quality_score": data.get("qa_report", {}).get("quality_score"),
        "grade": data.get("qa_report", {}).get("grade"),
        "latency_seconds": data.get("total_latency_seconds"),
        "server": f"proxy-{pid}",
        "hardware": data.get("hardware")
    }, indent=2)

@mcp.tool()
async def edit_image(
    image_path: str,
    prompt: str = "",
    filter_preset: str = "auto_enhance",
    brightness: float = 1.0,
    contrast: float = 1.0,
    sharpness: float = 1.0,
    strength: float = 0.65,
    steps: int = 15
) -> str:
    """Edit image via central Gemini Nano runtime engine on CPU."""
    if not (image_path.startswith("http://") or image_path.startswith("https://")):
        try:
            safe_path(image_path, must_exist=True)
        except (PathNotAllowed, FileNotFoundError) as e:
            raise ToolError(str(e))

    edit_mode = "ai_img2img" if (prompt and prompt.strip()) else "transform"
    payload = {
        "image_source": image_path,
        "prompt": prompt or None,
        "edit_mode": edit_mode,
        "filter_preset": filter_preset,
        "brightness": brightness,
        "contrast": contrast,
        "sharpness": sharpness,
        "strength": strength,
        "steps": steps,
        "run_qa": True
    }
    
    try:
        async with httpx.AsyncClient(timeout=600.0) as client:
            resp = await client.post(f"{RUNTIME_URL}/api/edit", json=payload)
    except Exception as e:
        raise ToolError(f"image runtime unavailable: {e}")

    if resp.status_code != 200:
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        raise ToolError(str(detail))

    try:
        data = resp.json()
    except Exception as e:
        raise ToolError(f"invalid JSON response from runtime: {e}")

    if data.get("status") == "error" or data.get("success") is False:
        detail = data.get("detail") or data.get("message") or data.get("error") or "image edit failed"
        raise ToolError(str(detail))

    return json.dumps(data, indent=2)

@mcp.tool()
def optimize_prompt(prompt: str, style: str = "photorealistic") -> str:
    """Optimize a user prompt using AI Engineer strategies and stylistic expansion."""
    opt = get_optimizer()
    res = opt.optimize(raw_prompt=prompt, style=style)
    return json.dumps(res, indent=2)

@mcp.tool()
def analyze_image_quality(image_path: str) -> str:
    """Perform comprehensive Quality Assurance critique on an image file."""
    if not (image_path.startswith("http://") or image_path.startswith("https://")):
        try:
            safe_path(image_path, must_exist=True)
        except (PathNotAllowed, FileNotFoundError) as e:
            raise ToolError(str(e))

    qa = get_qa()
    try:
        img = load_image_from_path_or_b64(image_path)
        res = qa.analyze_image(img)
    except Exception as e:
        raise ToolError(str(e))
    return json.dumps(res, indent=2)

@mcp.tool()
def get_hardware_status() -> str:
    """Get CPU/GPU hardware isolation status and thread telemetry."""
    hw = get_system_hardware_profile()
    return json.dumps(hw, indent=2)
