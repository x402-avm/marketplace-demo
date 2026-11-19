import pytest
import numpy as np
from PIL import Image

from app.agents.generator import (
    InferenceAgent,
    QwenImageEngine,
    TEXT_ENCODER_MODEL,
    DIT_BACKBONE_MODEL,
    VAE_MODEL,
    format_chatml_edit_prompt
)
from app.config import ASPECT_RATIOS

@pytest.mark.asyncio
async def test_text_to_image_generation():
    agent = InferenceAgent()
    img, meta = await agent.generate_text_to_image(
        prompt="a serene sunset over calm ocean waters",
        aspect_ratio="1:1",
        num_inference_steps=10,
        seed=42
    )
    assert isinstance(img, Image.Image)
    assert img.size == (512, 512)
    assert meta["aspect_ratio"] == "1:1"
    assert meta["device"] == "cpu"
    assert meta["latency_seconds"] > 0

@pytest.mark.asyncio
async def test_image_to_image_generation():
    agent = InferenceAgent()
    # Create input test image
    init_img = Image.new("RGB", (256, 256), color=(100, 150, 200))
    
    img, meta = await agent.generate_image_to_image(
        init_image=init_img,
        prompt="transform into vibrant autumn landscape",
        strength=0.5,
        num_inference_steps=10,
        seed=123
    )
    assert isinstance(img, Image.Image)
    assert img.size == (256, 256)
    assert meta["strength"] == 0.5
    assert meta["device"] == "cpu"

@pytest.mark.asyncio
async def test_aspect_ratios():
    agent = InferenceAgent()
    img_wide, _ = await agent.generate_text_to_image(prompt="car", aspect_ratio="16:9")
    assert img_wide.size == (768, 432)
    
    img_tall, _ = await agent.generate_text_to_image(prompt="portrait", aspect_ratio="9:16")
    assert img_tall.size == (432, 768)


def test_i2i_workflow_true_latent_vae_encoding():
    """Verify build_i2i_workflow uses genuine VAEEncode for latent input rather than torch.zeros."""
    engine = QwenImageEngine()
    wf = engine.build_i2i_workflow(
        prompt="add sunglasses to the character",
        negative_prompt="blurry",
        image_filename="ref_1.png",
        steps=20,
        seed=99,
        resolution=1024,
        strength=0.75
    )

    # VAEEncode must be present and connected to the input reference image (node 10) and VAE (node 3)
    assert "5" in wf
    assert wf["5"]["class_type"] == "VAEEncode"
    assert wf["5"]["inputs"]["pixels"] == ["10", 0]
    assert wf["5"]["inputs"]["vae"] == ["3", 0]

    # KSampler must receive VAEEncode latents (["5", 0]), NOT TextEncode zero latents (["4", 2])
    assert wf["6"]["class_type"] == "KSampler"
    assert wf["6"]["inputs"]["latent_image"] == ["5", 0]
    assert wf["6"]["inputs"]["latent_image"] != ["4", 2]
    assert wf["6"]["inputs"]["denoise"] == 0.75

    # Text encoder must run on CPU
    assert wf["2"]["class_type"] == "CLIPLoader"
    assert wf["2"]["inputs"]["device"] == "cpu"
    assert wf["2"]["inputs"]["clip_name"] == "qwen3vl_8b_bf16_heretic.safetensors"


def test_i2i_stage1_workflow_true_latent_vae_encoding():
    """Verify build_i2i_stage1_workflow encodes reference image via VAEEncode and saves it to stage cache."""
    engine = QwenImageEngine()
    stage_path = "/tmp/test_i2i_st1_verify.pt"
    wf = engine.build_i2i_stage1_workflow(
        prompt="turn background into tropical beach",
        negative_prompt="dark, gloomy",
        image_filenames=["ref_1.png"],
        resolution=1024,
        stage_file=stage_path
    )

    # VAEEncode node must be present
    assert "4b" in wf
    assert wf["4b"]["class_type"] == "VAEEncode"
    assert wf["4b"]["inputs"]["pixels"] == ["10", 0]
    assert wf["4b"]["inputs"]["vae"] == ["2", 0]

    # QwenStageSaveStage1 must save the VAEEncode output, NOT slot 2 of TextEncodeQwenImage21
    assert wf["5"]["class_type"] == "QwenStageSaveStage1"
    assert wf["5"]["inputs"]["latent"] == ["4b", 0]
    assert wf["5"]["inputs"]["latent"] != ["4", 2]
    assert wf["5"]["inputs"]["stage_file"] == stage_path

    # Stage 1 CLIPLoader must execute on CPU
    assert wf["1"]["class_type"] == "CLIPLoader"
    assert wf["1"]["inputs"]["device"] == "cpu"
    assert wf["1"]["inputs"]["clip_name"] == "qwen3vl_8b_bf16_heretic.safetensors"


def test_stage2_workflow_strength_denoise_scaling():
    """Verify build_stage2_workflow configures KSampler denoise strictly proportional to strength."""
    engine = QwenImageEngine()

    # User strength 0.35
    wf_edit = engine.build_stage2_workflow(
        stage1_file="/tmp/st1.pt",
        steps=25,
        seed=101,
        stage2_file="/tmp/st2.pt",
        denoise=0.35
    )
    assert wf_edit["3"]["class_type"] == "KSampler"
    assert wf_edit["3"]["inputs"]["denoise"] == 0.35
    assert wf_edit["2"]["inputs"]["unet_name"] == DIT_BACKBONE_MODEL

    # User strength 0.85
    wf_edit_heavy = engine.build_stage2_workflow(
        stage1_file="/tmp/st1.pt",
        steps=25,
        seed=101,
        stage2_file="/tmp/st2.pt",
        denoise=0.85
    )
    assert wf_edit_heavy["3"]["inputs"]["denoise"] == 0.85

    # Default T2I denoise must remain 1.0
    wf_t2i = engine.build_stage2_workflow(
        stage1_file="/tmp/st1.pt",
        steps=25,
        seed=101,
        stage2_file="/tmp/st2.pt"
    )
    assert wf_t2i["3"]["inputs"]["denoise"] == 1.0


def test_chatml_edit_instruction_formatting():
    """Verify official Qwen-VL ChatML image editing template is applied to edit prompts."""
    raw_prompt = "add a red hat and sunglasses"
    formatted = format_chatml_edit_prompt(raw_prompt, num_images=1)

    assert formatted.startswith("<|im_start|>system")
    assert "Describe the key features of the input image" in formatted
    assert "<|im_start|>user\nPicture 1: <|vision_start|><|image_pad|><|vision_end|>" in formatted
    assert "add a red hat and sunglasses" in formatted
    assert formatted.endswith("<|im_start|>assistant\n")

    # Verify idempotency (already-formatted prompt is not double-wrapped)
    idempotent = format_chatml_edit_prompt(formatted, num_images=1)
    assert idempotent == formatted

    # Verify workflow builder embeds ChatML format into TextEncodeQwenImage21 prompt input
    engine = QwenImageEngine()
    st1_wf = engine.build_i2i_stage1_workflow(
        prompt=raw_prompt,
        negative_prompt="",
        image_filenames=["img.png"],
        resolution=1024,
        stage_file="/tmp/st1.pt"
    )
    assert "<|im_start|>system" in st1_wf["4"]["inputs"]["prompt"]
    assert "Picture 1: <|vision_start|><|image_pad|><|vision_end|>" in st1_wf["4"]["inputs"]["prompt"]


def test_native_high_resolution_1024_scaling():
    """Verify native 1024x1024 scaling without 512 downsampling clamping."""
    assert "1024x1024" in ASPECT_RATIOS
    assert ASPECT_RATIOS["1024x1024"] == (1024, 1024)
    assert "1:1_1024" in ASPECT_RATIOS
    assert ASPECT_RATIOS["1:1_1024"] == (1024, 1024)
    assert "16:9_1024" in ASPECT_RATIOS
    assert ASPECT_RATIOS["16:9_1024"] == (1024, 576)
    assert "9:16_1024" in ASPECT_RATIOS
    assert ASPECT_RATIOS["9:16_1024"] == (576, 1024)

    engine = QwenImageEngine()
    # Verify build_i2i_stage1_workflow accepts and propagates resolution 1024
    wf = engine.build_i2i_stage1_workflow(
        prompt="high res edit",
        negative_prompt="",
        image_filenames=["img1024.png"],
        resolution=1024,
        stage_file="/tmp/st1.pt"
    )
    assert wf["4"]["inputs"]["resolution"] == 1024


def test_text_encoder_device_binding_cpu():
    """Verify TEXT_ENCODER_MODEL is configured as BF16 Heretic and CLIPLoader is bound to CPU."""
    assert TEXT_ENCODER_MODEL == "qwen3vl_8b_bf16_heretic.safetensors"

    engine = QwenImageEngine()
    t2i_st1 = engine.build_t2i_stage1_workflow(
        prompt="a peaceful garden",
        negative_prompt="",
        width=1024,
        height=1024,
        stage_file="/tmp/t2i_st1.pt"
    )
    assert t2i_st1["1"]["class_type"] == "CLIPLoader"
    assert t2i_st1["1"]["inputs"]["device"] == "cpu"
    assert t2i_st1["1"]["inputs"]["clip_name"] == TEXT_ENCODER_MODEL


@pytest.mark.asyncio
async def test_high_resolution_text_to_image_generation():
    """Verify InferenceAgent generates 1024x1024 image when requested."""
    agent = InferenceAgent()
    img, meta = await agent.generate_text_to_image(
        prompt="futuristic neon skyline at night",
        aspect_ratio="1024x1024",
        num_inference_steps=1,
        seed=88
    )
    assert isinstance(img, Image.Image)
    assert img.size == (1024, 1024)
    assert meta["aspect_ratio"] == "1024x1024"
    assert meta["width"] == 1024
    assert meta["height"] == 1024


def test_oom_guard_preflight_checks_and_graceful_rejection(monkeypatch):
    """Verify OOM Guard preflight checks are strictly enforced and reject when memory pressure exceeds limit."""
    from app.utils.oom_guard import oom_guard

    # 1. Verify preflight_check method exists and functions
    assert hasattr(oom_guard, "preflight_check")
    safe, reason = oom_guard.preflight_check()
    assert isinstance(safe, bool)
    assert isinstance(reason, str)

    # 2. Simulate critical memory pressure (96% RAM used)
    monkeypatch.setattr(oom_guard, "get_system_ram_percent", lambda: 96.0)
    monkeypatch.setattr(oom_guard, "get_available_memory_bytes", lambda: 500 * 1024 * 1024)

    rejected, reject_reason = oom_guard.preflight_check()
    assert rejected is False
    assert "System RAM is critically high" in reject_reason

    # 3. Verify generator engine rejects execution gracefully under memory pressure
    engine = QwenImageEngine()
    test_img = Image.new("RGB", (256, 256), color=(50, 100, 150))
    with pytest.raises(RuntimeError, match="Pre-flight rejection"):
        engine.edit_image_staged(
            prompt="add rainbow",
            image=test_img,
            steps=1
        )

    with pytest.raises(RuntimeError, match="Pre-flight rejection"):
        engine.generate_image_staged(
            prompt="sunny field",
            width=512,
            height=512,
            steps=1
        )


def test_stage_cache_intermediate_files_cleanup_on_error(monkeypatch):
    """Verify intermediate stage cache files are cleanly unlinked even if stage execution raises an error."""
    from app.config import STAGE_CACHE_DIR
    engine = QwenImageEngine()

    for f in STAGE_CACHE_DIR.glob("i2i_st*.pt"):
        try:
            f.unlink()
        except Exception:
            pass

    test_img = Image.new("RGB", (256, 256), color=(100, 100, 100))

    # Simulate an error during stage 1 queueing
    def faulty_queue(wf):
        raise RuntimeError("Simulated ComfyUI backend network failure during Stage 1")

    monkeypatch.setattr(engine, "ensure_backend_running", lambda: None)
    monkeypatch.setattr(engine, "upload_image_to_backend", lambda img, name: None)
    monkeypatch.setattr(engine, "queue_prompt", faulty_queue)

    with pytest.raises(RuntimeError, match="Simulated ComfyUI backend network failure"):
        engine._edit_image_staged(
            prompt="add snow",
            image=test_img,
            steps=1
        )

    # Verify no orphan staging files exist
    orphans = list(STAGE_CACHE_DIR.glob("i2i_st*.pt"))
    assert len(orphans) == 0, f"Found orphan staging files after error: {orphans}"

