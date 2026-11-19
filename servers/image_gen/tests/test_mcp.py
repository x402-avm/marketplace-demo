import pytest
import json
from app.mcp.server import (
    optimize_prompt,
    get_hardware_status,
    generate_image,
    edit_image,
    analyze_image_quality
)
from app.utils.image_utils import save_image_to_disk
from app.config import OUTPUTS_DIR
from PIL import Image

def test_mcp_optimize_prompt():
    raw_json = optimize_prompt("emerald dragon", "fantasy_oil")
    data = json.loads(raw_json)
    assert "optimized_prompt" in data
    assert "dragon" in data["optimized_prompt"]

def test_mcp_get_hardware_status():
    raw_json = get_hardware_status()
    data = json.loads(raw_json)
    assert data["dgpu_isolated"] is True
    assert data["device"] == "cpu"

@pytest.mark.asyncio
async def test_mcp_generate_image():
    raw_json = await generate_image(
        prompt="neon robot",
        style="cyberpunk",
        steps=10
    )
    data = json.loads(raw_json)
    assert data["status"] == "success"
    assert "file_path" in data
    assert data["quality_score"] > 0

@pytest.mark.asyncio
async def test_mcp_edit_image():
    # Save a small test image
    img = Image.new("RGB", (64, 64), color=(100, 150, 200))
    path = save_image_to_disk(img, OUTPUTS_DIR, "mcp_test_in.png")
    
    raw_json = await edit_image(
        image_path=str(path),
        filter_preset="cinematic",
        brightness=1.1
    )
    data = json.loads(raw_json)
    assert data["status"] == "success"
    assert "file_path" in data
