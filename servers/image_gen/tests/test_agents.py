import pytest
import os
from pathlib import Path
from PIL import Image
import numpy as np

from app.agents.prompt_optimizer import PromptOptimizerAgent, STYLE_PRESETS
from app.agents.qa_critic import QualityAssuranceAgent
from app.agents.generator import InferenceAgent
from app.agents.orchestrator import AgentOrchestrator
from app.config import OUTPUTS_DIR

def test_prompt_optimizer_styles():
    opt = PromptOptimizerAgent()
    for style_name in STYLE_PRESETS.keys():
        result = opt.optimize("a cybernetic astronaut", style=style_name)
        assert result["style_applied"] == style_name
        assert "cybernetic astronaut" in result["optimized_prompt"]
        assert len(result["negative_prompt"]) > 10
        assert result["recommended_steps"] == 15
        assert result["recommended_aspect_ratio"] in ("1:1", "16:9", "9:16", "4:3", "3:2")

def test_aspect_ratio_inference():
    opt = PromptOptimizerAgent()
    assert opt.infer_aspect_ratio("portrait of an elegant woman") == "9:16"
    assert opt.infer_aspect_ratio("wide panoramic mountain landscape at sunrise") == "16:9"
    assert opt.infer_aspect_ratio("abstract geometric cube logo") == "1:1"

def test_qa_critic_metrics():
    qa = QualityAssuranceAgent()
    # Create test image with distinct gradient
    arr = np.linspace(0, 255, 256 * 256).reshape((256, 256)).astype(np.uint8)
    img = Image.fromarray(arr).convert("RGB")
    
    report = qa.analyze_image(img)
    assert "quality_score" in report
    assert 0.0 <= report["quality_score"] <= 100.0
    assert report["grade"] in ("A+", "A", "B", "C")
    assert "sharpness" in report["metrics"]
    assert "contrast" in report["metrics"]
    assert "exposure" in report["metrics"]
    assert "vibrancy" in report["metrics"]
    assert isinstance(report["suggestions"], list)
    assert report["passed_qa"] is True

@pytest.mark.asyncio
async def test_inference_agent_text_to_image():
    agent = InferenceAgent()
    img, meta = await agent.generate_text_to_image(
        prompt="a golden sunset over rolling hills",
        aspect_ratio="1:1",
        num_inference_steps=5,
        seed=42
    )
    assert isinstance(img, Image.Image)
    assert img.size == (512, 512)
    assert meta["width"] == 512
    assert meta["height"] == 512
    assert meta["device"] == "cpu"
    assert meta["latency_seconds"] > 0

@pytest.mark.asyncio
async def test_inference_agent_seed_determinism():
    agent = InferenceAgent()
    img1, _ = await agent.generate_text_to_image(
        prompt="cyberpunk neon skyline",
        aspect_ratio="1:1",
        seed=1337
    )
    img2, _ = await agent.generate_text_to_image(
        prompt="cyberpunk neon skyline",
        aspect_ratio="1:1",
        seed=1337
    )
    arr1 = np.array(img1)
    arr2 = np.array(img2)
    assert np.array_equal(arr1, arr2), "Identical seed and prompt must produce identical outputs!"

@pytest.mark.asyncio
async def test_inference_agent_image_to_image():
    agent = InferenceAgent()
    base_img = Image.new("RGB", (256, 256), color=(100, 150, 200))
    img, meta = await agent.generate_image_to_image(
        init_image=base_img,
        prompt="turn into an oil painting",
        strength=0.5,
        seed=999
    )
    assert isinstance(img, Image.Image)
    assert img.size == (256, 256)
    assert meta["strength"] == 0.5
    assert meta["device"] == "cpu"

@pytest.mark.asyncio
async def test_agent_orchestrator_full_pipeline():
    orchestrator = AgentOrchestrator()
    result = await orchestrator.orchestrate_text_to_image(
        prompt="futuristic sports car in the rain",
        style="cinematic_8k",
        aspect_ratio="16:9",
        auto_optimize=True,
        run_qa=True,
        seed=101
    )
    assert result["success"] is True
    assert "gen_" in result["filename"]
    assert Path(result["file_path"]).is_file()
    assert result["image_base64"].startswith("data:image/png;base64,")
    assert result["qa_report"]["passed_qa"] is True
    assert len(result["audit_log"]) >= 3
    assert result["hardware"]["device"] == "cpu"
    assert result["hardware"]["dgpu_isolated"] is True
