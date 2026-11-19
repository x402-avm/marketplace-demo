import os
import time
import json
import pytest
import numpy as np
from PIL import Image
from unittest.mock import patch, AsyncMock, MagicMock

from app.agents.qa_critic import QualityAssuranceAgent, CritiqueResult, StageProfiler
from app.agents.prompt_optimizer import PromptOptimizerAgent
from app.agents.orchestrator import AgentOrchestrator
from app.utils.oom_guard import oom_guard
from app.config import STAGE_CACHE_DIR
from app.utils.image_utils import image_to_base64


@pytest.fixture
def qa_agent():
    return QualityAssuranceAgent()


@pytest.fixture
def prompt_optimizer():
    return PromptOptimizerAgent()


# ==============================================================================
# 1. Spatial Prompt Adherence Tests
# ==============================================================================

def test_spatial_prompt_adherence_basic(qa_agent):
    """Verify that spatial prompt adherence evaluates object attributes and prepositions."""
    # Create an image with a blue top half and a yellow bottom half
    arr = np.zeros((200, 200, 3), dtype=np.uint8)
    arr[:100, :] = [50, 100, 220]    # Blue top
    arr[100:, :] = [230, 220, 40]    # Yellow bottom
    img = Image.fromarray(arr)

    prompt = "a blue sphere on top of a yellow cube"
    result = qa_agent.evaluate_spatial_prompt_adherence(img, prompt)

    assert "adherence_score" in result
    assert 0.0 <= result["adherence_score"] <= 100.0
    assert result["entities_evaluated"] >= 2
    assert result["spatial_relations_evaluated"] >= 1
    assert "critique_notes" in result
    assert isinstance(result["passed_adherence"], bool)
    assert result["passed_adherence"] is True
    assert result["spatial_relations_passed"] >= 1


def test_spatial_prompt_adherence_inverted_vertical_fails(qa_agent):
    """Verify that spatial adherence correctly detects inverted vertical positions (e.g. blue on bottom instead of top)."""
    # Create an image where blue is at the BOTTOM and yellow is at the TOP
    arr = np.zeros((200, 200, 3), dtype=np.uint8)
    arr[:100, :] = [230, 220, 40]    # Yellow top
    arr[100:, :] = [50, 100, 220]    # Blue bottom
    img = Image.fromarray(arr)

    # Prompt asks for blue sphere on top of yellow cube
    prompt = "a blue sphere on top of a yellow cube"
    result = qa_agent.evaluate_spatial_prompt_adherence(img, prompt)

    # Spatial relation should FAIL because blue is below yellow
    assert result["spatial_relations_passed"] == 0
    assert any("Spatial violation" in note for note in result["critique_notes"])


def test_spatial_prompt_adherence_horizontal_relations(qa_agent):
    """Verify horizontal relative placement evaluation (left of / right of)."""
    # Image with blue on the left (x: 0..100) and red on the right (x: 100..200)
    arr = np.zeros((200, 200, 3), dtype=np.uint8)
    arr[:, :100] = [50, 100, 220]    # Blue left
    arr[:, 100:] = [220, 40, 50]     # Red right
    img = Image.fromarray(arr)

    prompt_correct = "a blue cube to the left of a red cylinder"
    result_correct = qa_agent.evaluate_spatial_prompt_adherence(img, prompt_correct)
    assert result_correct["spatial_relations_passed"] == 1
    assert result_correct["passed_adherence"] is True

    prompt_inverted = "a red cylinder to the left of a blue cube"
    result_inverted = qa_agent.evaluate_spatial_prompt_adherence(img, prompt_inverted)
    assert result_inverted["spatial_relations_passed"] == 0
    assert any("Spatial violation" in note for note in result_inverted["critique_notes"])


def test_spatial_prompt_adherence_attribute_binding_and_color_salience(qa_agent):
    """Verify entity-attribute binding penalizes low color salience when colors are missing."""
    # Monochromatic gray image
    img = Image.new("RGB", (200, 200), color=(128, 128, 128))
    prompt = "a blue bird on top of a yellow branch"
    result = qa_agent.evaluate_spatial_prompt_adherence(img, prompt)

    assert result["entity_attribute_binding_score"] < 50.0
    assert any("Attribute binding" in note for note in result["critique_notes"])


def test_spatial_prompt_adherence_no_relations(qa_agent):
    """Verify fallback behavior when prompt has no complex spatial relations."""
    img = Image.new("RGB", (100, 100), color=(128, 128, 128))
    prompt = "a solitary mountain"
    result = qa_agent.evaluate_spatial_prompt_adherence(img, prompt)

    assert result["adherence_score"] == 100.0
    assert result["passed_adherence"] is True
    assert result["spatial_relations_evaluated"] == 0


# ==============================================================================
# 2. Multi-Stage Resource & Latency Profiler Tests
# ==============================================================================

def test_multi_stage_resource_and_latency_profiler(qa_agent):
    """Verify stage profiler calculates bottlenecks, total latency, and OOM safety."""
    stage_metrics = {
        "stage_1_vision_text_encoder_seconds": 2.15,
        "stage_2_dit_sampling_seconds": 8.42,
        "stage_3_vae_decode_seconds": 0.68,
        "ram_usage_percent": 42.5,
        "vram_free_mb": 7800.0
    }

    profile = qa_agent.profile_stage_metrics(stage_metrics)
    assert "stage_timings_seconds" in profile
    assert profile["total_staged_latency_seconds"] == 11.25
    assert profile["bottleneck_stage"] == "stage_2_dit_sampling_seconds"
    assert profile["bottleneck_latency_seconds"] == 8.42
    assert profile["oom_safe"] is True
    assert profile["ram_usage_percent"] == 42.5

    # Enhanced millisecond and memory metrics
    assert "stage_latencies_ms" in profile
    assert profile["total_staged_latency_ms"] == 11250.0
    assert profile["stage_latencies_ms"]["stage_2_dit_sampling_ms"] == 8420.0
    assert "ram_metrics" in profile
    assert profile["ram_metrics"]["usage_percent"] == 42.5
    assert "vram_metrics" in profile
    assert profile["vram_metrics"]["free_mb"] == 7800.0
    assert "stages" in profile
    assert "stage_1_text_vision_encoding" in profile["stages"]
    assert "stage_2_dit_diffusion_sampling" in profile["stages"]
    assert "stage_3_vae_latent_decode" in profile["stages"]


def test_stage_profiler_oom_detection(qa_agent):
    """Verify that profiler flags unsafe RAM conditions when >= 90%."""
    unsafe_metrics = {
        "stage_1_seconds": 3.0,
        "ram_usage_percent": 92.4,
    }
    profile = qa_agent.profile_stage_metrics(unsafe_metrics)
    assert profile["oom_safe"] is False


def test_stage_profiler_context_manager():
    """Verify StageProfiler context manager records latency, RAM, and VRAM across stages."""
    profiler = StageProfiler()

    with profiler.profile_stage("stage_1_cpu_encode"):
        time.sleep(0.01)

    with profiler.profile_stage("stage_2_dgpu_dit"):
        time.sleep(0.04)

    summary = profiler.get_summary()
    assert len(summary["stage_records"]) == 2
    assert summary["total_staged_latency_ms"] >= 40.0
    assert summary["bottleneck_stage"] == "stage_2_dgpu_dit"
    assert summary["bottleneck_latency_ms"] > 0


def test_critique_result_dict_and_attribute_access(qa_agent):
    """Verify CritiqueResult provides transparent dict and dot-attribute access and is JSON serializable."""
    img = Image.new("RGB", (100, 100), color=(100, 120, 150))
    result = qa_agent.analyze_image(img)

    assert isinstance(result, CritiqueResult)
    assert isinstance(result, dict)
    # Dict access
    assert "quality_score" in result
    # Attribute access
    assert result.quality_score == result["quality_score"]
    assert result.grade == result["grade"]
    assert result.status == result["status"]
    assert result.passed_qa == result["passed_qa"]

    # Verify JSON serializability
    serialized = json.dumps(result)
    assert "quality_score" in serialized


def test_qa_analyze_image_with_prompt_and_metrics(qa_agent):
    """Verify that analyze_image integrates spatial adherence and stage profile."""
    img = Image.new("RGB", (128, 128), color=(100, 150, 200))
    prompt = "a blue bird on a green branch"
    metrics = {
        "stage_1_seconds": 1.2,
        "stage_2_seconds": 5.4,
        "ram_usage_percent": 35.0
    }

    report = qa_agent.analyze_image(img, prompt=prompt, stage_metrics=metrics)
    assert "quality_score" in report
    assert "spatial_adherence" in report
    assert "stage_profile" in report
    assert report["spatial_adherence"]["entities_evaluated"] >= 1
    assert report["stage_profile"]["bottleneck_stage"] == "stage_2_seconds"


# ==============================================================================
# 3. OOM Guard Pre-Flight & Orchestrator Integration Tests
# ==============================================================================

def test_oom_guard_preflight_checks():
    """Verify OOM Guard preflight checks pass under normal conditions and fail on threshold."""
    # Under normal condition:
    safe, reason = oom_guard.preflight_check()
    assert isinstance(safe, bool)
    assert isinstance(reason, str)

    # Simulated unsafe RAM:
    with patch.object(oom_guard, "get_system_ram_percent", return_value=96.0):
        unsafe, msg = oom_guard.preflight_check()
        assert unsafe is False
        assert "critically high" in msg or "OOM Fail-Safe Guard" in msg


@pytest.mark.asyncio
async def test_orchestrator_oom_guard_preflight_rejection():
    """Verify AgentOrchestrator rejects requests immediately if OOM Guard preflight fails."""
    orchestrator = AgentOrchestrator()

    with patch.object(oom_guard, "preflight_check", return_value=(False, "Memory critically exhausted (95.5% used)")):
        with pytest.raises(RuntimeError) as exc_info:
            await orchestrator.orchestrate_text_to_image(prompt="a futuristic hovercar")
        assert "OOM Guard Pre-flight Rejection" in str(exc_info.value)

        with pytest.raises(RuntimeError) as exc_info2:
            img = Image.new("RGB", (64, 64), color=(50, 50, 50))
            await orchestrator.orchestrate_image_edit(image_source=image_to_base64(img), prompt="add neon glow")
        assert "OOM Guard Pre-flight Rejection" in str(exc_info2.value)


@pytest.mark.asyncio
async def test_orchestrator_threads_strength_and_resolution():
    """Verify AgentOrchestrator threads strength and resolution to underlying engine."""
    mock_generator = MagicMock()
    mock_generator.generate_text_to_image = AsyncMock(return_value=(
        Image.new("RGB", (1024, 1024), color=(100, 100, 100)),
        {
            "width": 1024,
            "height": 1024,
            "latency_seconds": 1.5,
            "engine": "qwen2.1",
            "stage_metrics": {
                "stage_1_text_encoder_seconds": 0.4,
                "stage_2_dit_sampling_seconds": 1.0,
                "stage_3_vae_decode_seconds": 0.1,
                "ram_usage_percent": 38.0
            }
        }
    ))
    mock_generator.generate_image_to_image = AsyncMock(return_value=(
        Image.new("RGB", (1024, 1024), color=(120, 120, 120)),
        {
            "width": 1024,
            "height": 1024,
            "latency_seconds": 1.8,
            "strength": 0.45,
            "stage_metrics": {
                "stage_1_vision_text_encoder_seconds": 0.5,
                "stage_2_dit_sampling_seconds": 1.1,
                "stage_3_vae_decode_seconds": 0.2,
                "ram_usage_percent": 39.0
            }
        }
    ))

    orchestrator = AgentOrchestrator(generator=mock_generator)

    with patch.object(oom_guard, "preflight_check", return_value=(True, "OK")):
        # 1. Text to image with resolution 1024
        res_t2i = await orchestrator.orchestrate_text_to_image(
            prompt="majestic snowy peak at sunset",
            resolution=1024,
            run_qa=True
        )
        assert res_t2i["success"] is True
        assert "stage_metrics" in res_t2i
        assert res_t2i["qa_report"]["passed_qa"] is True
        mock_generator.generate_text_to_image.assert_called_once()
        call_kwargs = mock_generator.generate_text_to_image.call_args.kwargs
        assert call_kwargs["aspect_ratio"] in ("1024x1024", "1:1_1024")

        # 2. Image generation alias
        res_alias = await orchestrator.orchestrate_image_generation(
            prompt="majestic snowy peak at sunset",
            resolution=1024,
            run_qa=False
        )
        assert res_alias["success"] is True

        # 3. Image edit with strength 0.45 and resolution 1024
        sample_img = Image.new("RGB", (512, 512), color=(80, 80, 80))
        res_edit = await orchestrator.orchestrate_image_edit(
            image_source=image_to_base64(sample_img),
            prompt="add northern lights in the sky",
            strength=0.45,
            resolution=1024,
            run_qa=True
        )
        assert res_edit["success"] is True
        assert "stage_metrics" in res_edit
        mock_generator.generate_image_to_image.assert_called_once()
        edit_call_kwargs = mock_generator.generate_image_to_image.call_args.kwargs
        assert edit_call_kwargs["strength"] == 0.45


def test_stage_cache_directory_exists():
    """Ensure stage cache directory is configured and writable."""
    assert STAGE_CACHE_DIR.exists()
    assert os.access(str(STAGE_CACHE_DIR), os.W_OK)


def test_orchestrator_clear_cache_removes_intermediate_files():
    """Verify orchestrator clear_cache purges staging artifacts in outputs/.stage_cache."""
    orchestrator = AgentOrchestrator()
    dummy_st1 = STAGE_CACHE_DIR / "t2i_st1_test_eval_dummy.pt"
    dummy_st2 = STAGE_CACHE_DIR / "t2i_st2_test_eval_dummy.pt"

    dummy_st1.write_text("stage1 test tensor payload")
    dummy_st2.write_text("stage2 test tensor payload")
    assert dummy_st1.exists()
    assert dummy_st2.exists()

    cleared = orchestrator.clear_cache()
    assert cleared >= 2
    assert not dummy_st1.exists()
    assert not dummy_st2.exists()


@pytest.mark.asyncio
async def test_orchestrator_cache_cleanup_on_exception():
    """Verify intermediate cache files are unlinked even if generation raises an exception."""
    mock_generator = MagicMock()
    mock_generator.generate_text_to_image = AsyncMock(side_effect=RuntimeError("Simulated pipeline GPU error"))

    orchestrator = AgentOrchestrator(generator=mock_generator)

    # Seed intermediate file
    dummy_st1 = STAGE_CACHE_DIR / "t2i_st1_exception_test.pt"
    dummy_st1.write_text("transient tensor bytes")
    assert dummy_st1.exists()

    with patch.object(oom_guard, "preflight_check", return_value=(True, "OK")):
        with pytest.raises(RuntimeError) as exc_info:
            await orchestrator.orchestrate_text_to_image(prompt="test prompt")
        assert "Simulated pipeline GPU error" in str(exc_info.value)

    # Must be unlinked in finally block
    assert not dummy_st1.exists()
