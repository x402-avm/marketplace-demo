import pytest
import os
from PIL import Image
from app.agents.orchestrator import AgentOrchestrator
from app.utils.image_utils import image_to_base64

@pytest.fixture
def orchestrator():
    return AgentOrchestrator()

@pytest.mark.asyncio
async def test_orchestrate_text_to_image(orchestrator):
    result = await orchestrator.orchestrate_text_to_image(
        prompt="cyberpunk motorcycle in rain",
        style="cyberpunk",
        aspect_ratio="1:1",
        num_inference_steps=10,
        seed=999,
        auto_optimize=True,
        run_qa=True
    )
    assert result["success"] is True
    assert os.path.exists(result["file_path"])
    assert result["image_base64"].startswith("data:image/png;base64,")
    assert "qa_report" in result
    assert result["qa_report"]["quality_score"] > 0
    assert len(result["audit_log"]) >= 3
    assert result["hardware"]["dgpu_isolated"] is True

@pytest.mark.asyncio
async def test_orchestrate_image_edit(orchestrator):
    # Create sample textured base64 image
    import numpy as np
    arr = np.linspace(0, 255, 128 * 128).reshape((128, 128)).astype(np.uint8)
    img = Image.fromarray(arr).convert("RGB")
    b64 = image_to_base64(img)
    
    result = await orchestrator.orchestrate_image_edit(
        image_source=b64,
        filter_preset="cinematic",
        brightness=1.1,
        contrast=1.2,
        sharpness=1.5,
        run_qa=True
    )
    assert result["success"] is True
    assert os.path.exists(result["file_path"])
    assert result["qa_report"]["passed_qa"] is True
