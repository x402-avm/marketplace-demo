import json
from fastmcp import FastMCP
from app.agents import (
    AgentOrchestrator,
    PromptOptimizerAgent,
    QualityAssuranceAgent
)
from app.utils.hardware import get_system_hardware_profile
from app.utils.image_utils import load_image_from_path_or_b64

mcp = FastMCP("Gemini Nano Image Engine MCP")
orchestrator = AgentOrchestrator()
optimizer = PromptOptimizerAgent()
qa_critic = QualityAssuranceAgent()

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
    """Generate an image on AMD Ryzen AI 9 HX 370 CPU with multi-agent orchestration.
    
    Args:
        prompt: Text description of the desired image.
        style: Aesthetic preset ('photorealistic', 'cinematic_8k', 'anime_manga', 'studio_portrait', 'cyberpunk', 'fantasy_oil', 'minimalist_vector', 'analog_film').
        negative_prompt: Items or defects to exclude.
        aspect_ratio: '1:1', '16:9', '9:16', '4:3', or '3:2'.
        steps: Inference steps (CPU tuned, 10-25).
        guidance_scale: Classifier-free guidance scale.
        seed: Random seed (-1 for random).
        auto_optimize: Whether the AI Prompt Engineer agent enriches the prompt.
    """
    actual_seed = None if seed < 0 else seed
    result = await orchestrator.orchestrate_text_to_image(
        prompt=prompt,
        style=style,
        negative_prompt=negative_prompt,
        aspect_ratio=aspect_ratio,
        num_inference_steps=steps,
        guidance_scale=guidance_scale,
        seed=actual_seed,
        auto_optimize=auto_optimize,
        run_qa=True
    )
    return json.dumps({
        "status": "success",
        "file_path": result["file_path"],
        "filename": result["filename"],
        "quality_score": result["qa_report"].get("quality_score"),
        "grade": result["qa_report"].get("grade"),
        "latency_seconds": result["total_latency_seconds"],
        "prompt_used": result["prompt_used"],
        "hardware": result["hardware"]
    }, indent=2)

@mcp.tool()
async def edit_image(
    image_path: str,
    prompt: str = "",
    filter_preset: str = "auto_enhance",
    brightness: float = 1.0,
    contrast: float = 1.0,
    saturation: float = 1.0,
    sharpness: float = 1.0,
    strength: float = 0.65,
    steps: int = 15
) -> str:
    """Edit an existing image using AI Image-to-Image and high-performance CPU filters.
    
    Args:
        image_path: Absolute path to the source image.
        prompt: Optional AI prompt for generative transformation.
        filter_preset: Preset filter ('auto_enhance', 'cinematic', 'hdr', 'noir', 'portrait_bokeh', 'warm_golden', 'cool_neon', 'vintage', 'pencil_sketch', 'edge_detect').
        brightness: Brightness multiplier (0.5 to 2.0).
        contrast: Contrast multiplier (0.5 to 2.0).
        saturation: Saturation multiplier (0.0 to 2.0).
        sharpness: Sharpness multiplier (0.0 to 3.0).
        strength: Diffusion transformation strength (0.0 to 1.0).
        steps: Inference steps for diffusion edit (default: 15).
    """
    edit_mode = "ai_img2img" if (prompt and prompt.strip()) else "transform"
    result = await orchestrator.orchestrate_image_edit(
        image_source=image_path,
        prompt=prompt,
        edit_mode=edit_mode,
        filter_preset=filter_preset,
        brightness=brightness,
        contrast=contrast,
        saturation=saturation,
        sharpness=sharpness,
        strength=strength,
        steps=steps,
        run_qa=True
    )
    return json.dumps({
        "status": "success",
        "file_path": result["file_path"],
        "filename": result["filename"],
        "quality_score": result["qa_report"].get("quality_score"),
        "grade": result["qa_report"].get("grade"),
        "latency_seconds": result["total_latency_seconds"],
        "hardware": result["hardware"]
    }, indent=2)

@mcp.tool()
def optimize_prompt(prompt: str, style: str = "photorealistic") -> str:
    """Optimize a user prompt using AI Engineer strategies and stylistic expansion."""
    res = optimizer.optimize(raw_prompt=prompt, style=style)
    return json.dumps(res, indent=2)

@mcp.tool()
def analyze_image_quality(image_path: str) -> str:
    """Perform comprehensive Quality Assurance critique on an image file."""
    img = load_image_from_path_or_b64(image_path)
    res = qa_critic.analyze_image(img)
    return json.dumps(res, indent=2)

@mcp.tool()
def get_hardware_status() -> str:
    """Get CPU/GPU hardware isolation status and thread telemetry."""
    hw = get_system_hardware_profile()
    return json.dumps(hw, indent=2)
