import pytest
import json
from app.mcp.server import mcp, generate_image, edit_image, optimize_prompt, analyze_image_quality, get_hardware_status
from app.config import MCP_PORT

def test_mcp_port_in_range():
    assert 10000 <= MCP_PORT <= 10100, f"MCP_PORT {MCP_PORT} not in user required range [10000, 10100]"

@pytest.mark.asyncio
async def test_mcp_tool_registration():
    # Verify tools registered in fastmcp instance
    tools = await mcp.list_tools()
    tool_names = [tool.name for tool in tools]
    assert "generate_image" in tool_names
    assert "edit_image" in tool_names
    assert "optimize_prompt" in tool_names
    assert "analyze_image_quality" in tool_names
    assert "get_hardware_status" in tool_names

@pytest.mark.asyncio
async def test_mcp_generate_image_tool():
    res_str = await generate_image(
        prompt="A cute fluffy kitten playing with yarn",
        style="anime_manga",
        aspect_ratio="1:1",
        steps=5,
        seed=123
    )
    data = json.loads(res_str)
    assert data["status"] == "success"
    assert "filename" in data
    assert data["hardware"]["device"] == "cpu"
    assert data["hardware"]["dgpu_isolated"] is True

@pytest.mark.asyncio
async def test_mcp_edit_image_tool():
    # First generate
    res_str = await generate_image(
        prompt="Golden retriever in a park",
        style="photorealistic",
        steps=5,
        seed=456
    )
    data = json.loads(res_str)
    file_path = data["file_path"]
    
    # Now edit
    edit_str = await edit_image(
        image_path=file_path,
        filter_preset="cinematic",
        brightness=1.1,
        contrast=1.2
    )
    edit_data = json.loads(edit_str)
    assert edit_data["status"] == "success"
    assert "file_path" in edit_data
    assert edit_data["hardware"]["dgpu_isolated"] is True

def test_mcp_optimize_prompt_tool():
    res_str = optimize_prompt("emerald dragon perched on obsidian cliff", style="fantasy_oil")
    data = json.loads(res_str)
    assert "optimized_prompt" in data
    assert "Classical fantasy oil painting of" in data["optimized_prompt"]

def test_mcp_get_hardware_status_tool():
    res_str = get_hardware_status()
    data = json.loads(res_str)
    assert data["device"] == "cpu"
    assert data["dgpu_isolated"] is True
    assert data["torch_threads"] >= 4
