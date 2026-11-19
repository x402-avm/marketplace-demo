import os
import time
import asyncio
import pytest
from pathlib import Path
from PIL import Image

from app.agents.generator import QwenImageEngine, InferenceAgent, TEXT_ENCODER_MODEL, DIT_BACKBONE_MODEL, VAE_MODEL
from app.config import STAGE_CACHE_DIR, STAGE_BY_STAGE_PIPELINE, COMFY_DIR
from app.utils.oom_guard import oom_guard

comfy_missing = COMFY_DIR is None or not (COMFY_DIR / "main.py").is_file()
skip_no_comfy = pytest.mark.skipif(comfy_missing, reason="ComfyUI backend not installed (COMFY_DIR/main.py missing)")

def test_stage_pipeline_configuration():
    """Verify stage-by-stage pipeline configuration flags and paths."""
    assert STAGE_BY_STAGE_PIPELINE is True
    assert STAGE_CACHE_DIR.exists()
    assert str(STAGE_CACHE_DIR).endswith(".stage_cache")

def test_stage_workflow_builders_isolation():
    """Verify that stage workflow builders only contain the single active stage model."""
    engine = QwenImageEngine()

    # Stage 1: Must contain CLIPLoader, must NOT contain UNETLoader or VAELoader (in T2I)
    st1 = engine.build_t2i_stage1_workflow(
        prompt="test prompt",
        negative_prompt="",
        width=512,
        height=512,
        stage_file="/tmp/test_st1.pt"
    )
    class_types = [node["class_type"] for node in st1.values()]
    assert "CLIPLoader" in class_types
    assert "UNETLoader" not in class_types
    assert "VAELoader" not in class_types
    assert "TextEncodeQwenImage21" in class_types
    assert "QwenStageSaveStage1" in class_types

    # Stage 2: Must contain UNETLoader, must NOT contain CLIPLoader or VAELoader
    st2 = engine.build_stage2_workflow(
        stage1_file="/tmp/test_st1.pt",
        steps=5,
        seed=42,
        stage2_file="/tmp/test_st2.pt"
    )
    class_types_2 = [node["class_type"] for node in st2.values()]
    assert "UNETLoader" in class_types_2
    assert "CLIPLoader" not in class_types_2
    assert "VAELoader" not in class_types_2
    assert "QwenStageLoadStage1" in class_types_2
    assert "KSampler" in class_types_2
    assert "QwenStageSaveStage2" in class_types_2
    assert "QwenImage21Cache" in class_types_2

    # Stage 3: Must contain VAELoader, must NOT contain CLIPLoader or UNETLoader
    st3 = engine.build_stage3_workflow(
        stage2_file="/tmp/test_st2.pt",
        filename_prefix="Qwen21_Engine/T2I"
    )
    class_types_3 = [node["class_type"] for node in st3.values()]
    assert "VAELoader" in class_types_3
    assert "CLIPLoader" not in class_types_3
    assert "UNETLoader" not in class_types_3
    assert "QwenStageLoadStage2" in class_types_3
    assert "VAEDecode" in class_types_3
    assert "SaveImage" in class_types_3

def test_i2i_stage1_workflow_builder():
    """Verify I2I Stage 1 connects vision input without loading UNET."""
    engine = QwenImageEngine()
    st1_i2i = engine.build_i2i_stage1_workflow(
        prompt="edit test",
        negative_prompt="",
        image_filenames=["ref_1.png", "ref_2.png"],
        resolution=512,
        stage_file="/tmp/test_i2i_st1.pt"
    )
    class_types = [node["class_type"] for node in st1_i2i.values()]
    assert "CLIPLoader" in class_types
    assert "VAELoader" in class_types
    assert "LoadImage" in class_types
    assert "UNETLoader" not in class_types
    assert "QwenStageSaveStage1" in class_types

@pytest.mark.asyncio
async def test_inference_agent_stage_metadata():
    """Verify that InferenceAgent returns complete stage-by-stage telemetry and memory profiles."""
    agent = InferenceAgent()
    img, meta = await agent.generate_text_to_image(
        prompt="stage metadata check",
        aspect_ratio="1:1",
        num_inference_steps=5,
        seed=77
    )
    assert isinstance(img, Image.Image)
    assert "pipeline_mode" in meta
    assert meta["pipeline_mode"] == "sequential_stages"
    assert "pipeline_stages" in meta
    assert len(meta["pipeline_stages"]) == 3
    assert "stage_latencies" in meta
    assert "stage_memory_profile" in meta

@skip_no_comfy
@pytest.mark.asyncio
async def test_live_staged_t2i_execution_latency_and_oom_guard():
    """Execute live stage-by-stage T2I generation and prove it completes under 150-200s SLA with OOM stability."""
    engine = QwenImageEngine()
    if not engine.is_backend_running():
        engine.ensure_backend_running()

    # Ensure clean staging directory before test
    for f in STAGE_CACHE_DIR.glob("t2i_st*.pt"):
        try:
            f.unlink()
        except Exception:
            pass

    t_start = time.time()
    out_img = engine.generate_image_staged(
        prompt="a majestic snow-capped mountain under golden sunrise",
        negative_prompt="blurry",
        width=512,
        height=512,
        steps=1,
        seed=101
    )
    elapsed = time.time() - t_start

    assert isinstance(out_img, Image.Image)
    assert out_img.size == (512, 512)
    # SLA Check: must be strictly under 150-200 seconds
    assert elapsed <= 200.0, f"Execution time {elapsed:.2f}s exceeded 200s SLA!"

    # Memory Check: verify metrics tracked
    metrics = engine.last_stage_metrics
    assert "latencies" in metrics
    assert "memory_profile" in metrics
    profile = metrics["memory_profile"]
    assert profile["peak_ram_percent"] < oom_guard.max_ram_percent
    assert profile["oom_guard_status"] == "stable"
    assert profile["sla_compliant"] is True

    # Check staging cleanup: no orphan staging files
    staging_files = list(STAGE_CACHE_DIR.glob("t2i_st*.pt"))
    assert len(staging_files) == 0, f"Intermediate staging files were not cleaned up: {staging_files}"

@skip_no_comfy
@pytest.mark.asyncio
async def test_live_staged_i2i_execution_latency_and_cleanup():
    """Execute live stage-by-stage I2I editing and prove it completes under 150-200s SLA with OOM stability."""
    engine = QwenImageEngine()
    if not engine.is_backend_running():
        engine.ensure_backend_running()

    # Ensure clean staging directory before test
    for f in STAGE_CACHE_DIR.glob("i2i_st*.pt"):
        try:
            f.unlink()
        except Exception:
            pass

    input_img = Image.new("RGB", (256, 256), color=(60, 120, 180))
    t_start = time.time()
    edited_img = engine.edit_image_staged(
        prompt="transform into warm evening glow",
        negative_prompt="dark, noisy",
        image=input_img,
        steps=1,
        seed=202
    )
    elapsed = time.time() - t_start

    assert isinstance(edited_img, Image.Image)
    assert edited_img.size == (256, 256)
    # SLA Check: must be strictly under 150-200 seconds
    assert elapsed <= 200.0, f"Execution time {elapsed:.2f}s exceeded 200s SLA!"

    # Memory Check
    metrics = engine.last_stage_metrics
    profile = metrics["memory_profile"]
    assert profile["peak_ram_percent"] < oom_guard.max_ram_percent
    assert profile["oom_guard_status"] == "stable"

    # Check staging cleanup
    staging_files = list(STAGE_CACHE_DIR.glob("i2i_st*.pt"))
    assert len(staging_files) == 0, f"Intermediate I2I staging files were not cleaned up: {staging_files}"

@pytest.mark.asyncio
async def test_concurrent_multi_agent_pipeline_execution():
    """Verify that multiple concurrent agent requests execute safely without collision or OOM."""
    agent1 = InferenceAgent()
    agent2 = InferenceAgent()
    agent3 = InferenceAgent()

    ref_img = Image.new("RGB", (256, 256), color=(40, 80, 140))

    # Launch three concurrent agents (generation, editing, generation)
    task1 = agent1.generate_text_to_image(
        prompt="agent 1 cyber sunset",
        aspect_ratio="1:1",
        num_inference_steps=1,
        seed=301
    )
    task2 = agent2.generate_image_to_image(
        init_image=ref_img,
        prompt="agent 2 neon glow overhaul",
        num_inference_steps=1,
        seed=302
    )
    task3 = agent3.generate_text_to_image(
        prompt="agent 3 mountain peak",
        aspect_ratio="1:1",
        num_inference_steps=1,
        seed=303
    )

    (img1, meta1), (img2, meta2), (img3, meta3) = await asyncio.gather(task1, task2, task3)
    assert isinstance(img1, Image.Image)
    assert isinstance(img2, Image.Image)
    assert isinstance(img3, Image.Image)
    assert img1.size == (512, 512)
    assert img2.size == (256, 256)
    assert img3.size == (512, 512)
    assert meta1["pipeline_mode"] == "sequential_stages"
    assert meta2["pipeline_mode"] == "sequential_stages"
    assert meta3["pipeline_mode"] == "sequential_stages"
    assert oom_guard.get_system_ram_percent() < oom_guard.max_ram_percent

    # Verify no orphan staging or reference files left behind
    staging_files = list(STAGE_CACHE_DIR.glob("*.pt"))
    assert len(staging_files) == 0, f"Found orphan staging files: {staging_files}"
