import io
import os
import json
import pytest
from pathlib import Path
from PIL import Image
from fastapi.testclient import TestClient
from fastmcp.exceptions import ToolError

from app.main import app
from app.config import OUTPUTS_DIR
from app.utils.image_utils import (
    load_image_from_path_or_b64,
    image_to_base64,
    save_image_to_disk
)
from app.agents.generator import InferenceAgent
import mcp_server_1
import mcp_server_2
import mcp_server_3

client = TestClient(app)

def test_load_image_by_filename_in_outputs():
    """Ensure load_image_from_path_or_b64 finds files by simple filename in OUTPUTS_DIR."""
    test_img = Image.new("RGB", (64, 64), color=(20, 180, 80))
    test_filename = "test_edge_lookup.png"
    save_image_to_disk(test_img, OUTPUTS_DIR, test_filename)

    # 1. Test by filename only
    loaded = load_image_from_path_or_b64(test_filename)
    assert loaded.size == (64, 64)

    # 2. Test by /api/image/ URL
    loaded_url = load_image_from_path_or_b64(f"/api/image/{test_filename}")
    assert loaded_url.size == (64, 64)

def test_load_image_long_file_path_not_treated_as_base64(tmp_path):
    """Ensure file paths with >200 chars are not blindly treated as base64."""
    # Create deep path > 200 chars
    long_dir = tmp_path / ("dir_" + "x" * 150)
    long_dir.mkdir(parents=True, exist_ok=True)
    long_file = long_dir / ("sample_image_" + "y" * 60 + ".png")
    
    assert len(str(long_file)) > 200
    test_img = Image.new("RGB", (32, 32), color=(50, 100, 150))
    test_img.save(long_file)

    loaded = load_image_from_path_or_b64(str(long_file))
    assert loaded.size == (32, 32)

def test_load_image_invalid_inputs_raise():
    """Empty or None image source should raise ValueError."""
    with pytest.raises(ValueError):
        load_image_from_path_or_b64("")

    with pytest.raises(FileNotFoundError):
        load_image_from_path_or_b64("completely_nonexistent_image_file_12345.png")

def test_api_edit_and_qa_error_status_codes():
    """Missing or invalid image should return 404/400 rather than 500."""
    # 404 for missing file
    resp_404 = client.post("/api/edit", json={
        "image_source": "nonexistent_file_xyz.png",
        "filter_preset": "noir"
    })
    assert resp_404.status_code == 404
    assert "Image not found" in resp_404.json()["detail"]

    # 404 for missing file in QA
    qa_404 = client.post("/api/qa", json={
        "image_source": "nonexistent_file_xyz.png"
    })
    assert qa_404.status_code == 404

    # 400 for empty string
    resp_400 = client.post("/api/edit", json={
        "image_source": "",
        "filter_preset": "cinematic"
    })
    assert resp_400.status_code == 400

@pytest.mark.asyncio
async def test_inference_agent_tiny_image_img2img():
    """Ensure generate_image_to_image does not crash with zero-dimension on tiny images (<8px)."""
    gen = InferenceAgent()
    tiny_img = Image.new("RGB", (4, 4), color=(255, 0, 0))
    out_img, meta = await gen.generate_image_to_image(
        init_image=tiny_img,
        prompt="enhance details",
        strength=0.5
    )
    assert out_img.width >= 64
    assert out_img.height >= 64
    assert meta["device"] == "cpu"

@pytest.mark.asyncio
async def test_mcp_proxy_servers_have_full_tool_suite():
    """Ensure mcp_server_1, mcp_server_2, and mcp_server_3 expose all required tools."""
    for idx, srv in enumerate([mcp_server_1, mcp_server_2, mcp_server_3], start=1):
        tools = await srv.mcp.list_tools()
        tool_names = [t.name for t in tools]
        assert "generate_image" in tool_names, f"mcp_server_{idx} missing generate_image"
        assert "edit_image" in tool_names, f"mcp_server_{idx} missing edit_image"
        assert "optimize_prompt" in tool_names, f"mcp_server_{idx} missing optimize_prompt"
        assert "analyze_image_quality" in tool_names, f"mcp_server_{idx} missing analyze_image_quality"
        assert "get_hardware_status" in tool_names, f"mcp_server_{idx} missing get_hardware_status"

@pytest.mark.asyncio
async def test_mcp_servers_local_fallback_and_file_saving():
    """Ensure generate_image on mcp_server_1 raises ToolError when runtime is down, and does not litter root."""
    with pytest.raises(ToolError, match="image runtime unavailable"):
        await mcp_server_1.generate_image(
            prompt="Golden sunset over ocean horizon",
            style="photorealistic",
            steps=5,
            seed=42
        )
    assert not os.path.exists(mcp_server_1.BASE_DIR / "output_image_1.png")
