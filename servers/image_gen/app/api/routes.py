import os
from pathlib import Path
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.config import OUTPUTS_DIR, ASPECT_RATIOS
from app.agents import (
    AgentOrchestrator,
    PromptOptimizerAgent,
    QualityAssuranceAgent,
    STYLE_PRESETS
)
from app.storage import (
    ChatStore,
    default_store as chat_store,
    create_session,
    list_sessions,
    get_session,
    update_session,
    delete_session,
    add_message,
    set_active_context
)
from app.utils.hardware import get_system_hardware_profile
from app.utils.image_utils import load_image_from_path_or_b64
from app.utils.oom_guard import oom_guard

router = APIRouter()
orchestrator = AgentOrchestrator()
optimizer = PromptOptimizerAgent()
qa_critic = QualityAssuranceAgent()

# Request Models
class OptimizeRequest(BaseModel):
    prompt: str = Field(..., description="Raw text prompt")
    style: Optional[str] = Field("photorealistic", description="Style preset")
    negative_prompt: Optional[str] = Field(None, description="Additional negative prompt")
    aspect_ratio: Optional[str] = Field(None, description="Aspect ratio")

class GenerateRequest(BaseModel):
    prompt: str = Field(..., description="Text prompt for image generation")
    style: str = Field("photorealistic", description="Style aesthetic preset")
    negative_prompt: str = Field("", description="Negative prompt")
    aspect_ratio: str = Field("1:1", description="1:1, 16:9, 9:16, 4:3, or 3:2")
    steps: int = Field(15, ge=1, le=50, description="Inference steps")
    guidance_scale: float = Field(7.5, ge=1.0, le=20.0, description="Guidance scale")
    seed: Optional[int] = Field(None, description="Random seed")
    auto_optimize: bool = Field(True, description="Enable AI Prompt Engineer optimization")
    run_qa: bool = Field(True, description="Enable automated QA audit")
    session_id: Optional[str] = Field(None, description="Optional chat session ID for auto-logging and context tracking")
    image_sources: Optional[List[str]] = Field(None, description="Optional multiple reference images for multi-image in-context conditioning")

class EditRequest(BaseModel):
    image_source: Optional[str] = Field(None, description="Base64 data URL or filename/path (or uses active session image)")
    image_sources: Optional[List[str]] = Field(None, description="Optional list of multiple input images to blend, compose, or edit")
    mask_source: Optional[str] = Field(None, description="Optional Base64 data URL mask (white=edit, black=preserve)")
    prompt: Optional[str] = Field(None, description="Optional prompt for AI img2img synthesis")
    edit_mode: str = Field("transform", description="'transform' (CV filters/adjustments) or 'ai_img2img'")
    steps: int = Field(15, ge=1, le=50, description="Inference steps for AI img2img synthesis")
    filter_preset: Optional[str] = Field(None, description="Aesthetic preset filter name")
    brightness: float = Field(1.0, ge=0.1, le=3.0)
    contrast: float = Field(1.0, ge=0.1, le=3.0)
    saturation: float = Field(1.0, ge=0.0, le=3.0)
    sharpness: float = Field(1.0, ge=0.0, le=4.0)
    blur: float = Field(0.0, ge=0.0, le=25.0)
    vignette: float = Field(0.0, ge=0.0, le=1.0)
    gamma: float = Field(1.0, ge=0.2, le=3.0)
    strength: float = Field(0.65, ge=0.0, le=1.0)
    run_qa: bool = Field(True)
    session_id: Optional[str] = Field(None, description="Optional chat session ID for auto-logging and context tracking")
    edit_parent_id: Optional[str] = Field(None, description="Optional parent message ID being modified")

class QARequest(BaseModel):
    image_source: str = Field(..., description="Base64 data URL or file path to evaluate")

class CreateSessionRequest(BaseModel):
    title: Optional[str] = Field(None, description="Optional custom session title")

class UpdateSessionRequest(BaseModel):
    title: Optional[str] = Field(None, description="Updated session title")
    active_image_path: Optional[str] = Field(None, description="Active reference image path")

class AddMessageRequest(BaseModel):
    role: str = Field(..., description="Message role: 'user' or 'assistant'")
    content: str = Field(..., description="Message text content")
    image_path: Optional[str] = Field(None, description="Optional local file path to image")
    image_url: Optional[str] = Field(None, description="Optional URL to image")
    edit_parent_id: Optional[str] = Field(None, description="Optional parent message ID if this is an edit step")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Optional generation or QA metadata")


@router.get("/health")
@router.head("/health")
def health():
    hw = get_system_hardware_profile()
    mem_status = oom_guard.get_status()
    return {
        "status": "healthy",
        "service": "Gemini Nano Image Engine",
        "version": "2.0.0",
        "cpu_model": hw["cpu_model"],
        "dgpu_isolated": hw["dgpu_isolated"],
        "device": hw["device"],
        "system_ram_used_percent": mem_status["system_ram_used_percent"],
        "oom_guard_active": mem_status["oom_guard_active"],
        "oom_shutdown_threshold_percent": mem_status["emergency_shutdown_threshold_percent"]
    }

@router.get("/api/system")
@router.get("/api/hardware")
def get_system():
    profile = get_system_hardware_profile()
    profile["oom_guard"] = oom_guard.get_status()
    return profile

@router.get("/api/memory")
def get_memory_telemetry():
    """Live system RAM telemetry and OOM fail-safe status."""
    return oom_guard.get_status()

@router.get("/api/models")
def get_models():
    return {
        "models": [
            {
                "id": "qwen2.1-heretic-nvfp4",
                "name": "Qwen 2.1 Heretic NVFP4",
                "architecture": "NVFP4 Hybrid Latent Engine",
                "backend": "CPU (Zen 5 AVX-512)",
                "hardware": "AMD Ryzen AI 9 HX 370",
                "status": "ready"
            }
        ],
        "default": "qwen2.1-heretic-nvfp4"
    }

@router.get("/api/presets")
def get_presets():
    return {
        "styles": list(STYLE_PRESETS.keys()),
        "filters": [
            "none", "cinematic", "hdr", "noir", "portrait_bokeh",
            "warm_golden", "cool_neon", "vintage", "pencil_sketch",
            "edge_detect", "auto_enhance"
        ],
        "aspect_ratios": list(ASPECT_RATIOS.keys())
    }

@router.post("/api/optimize")
def optimize_prompt(req: OptimizeRequest):
    return optimizer.optimize(
        raw_prompt=req.prompt,
        style=req.style,
        negative_prompt=req.negative_prompt,
        custom_aspect_ratio=req.aspect_ratio
    )

@router.post("/api/generate")
async def generate_image(req: GenerateRequest):
    try:
        # Pre-flight OOM Fail-Safe check (reject if system RAM >= 90% to prevent laptop freeze)
        mem_ok, mem_reason = oom_guard.check_memory_preflight()
        if not mem_ok:
            raise HTTPException(status_code=503, detail=mem_reason)

        chat_history = None
        if req.session_id:
            sess = chat_store.get_session(req.session_id)
            if sess:
                chat_history = sess.get("messages", [])

        result = await orchestrator.orchestrate_text_to_image(
            prompt=req.prompt,
            style=req.style,
            negative_prompt=req.negative_prompt,
            aspect_ratio=req.aspect_ratio,
            num_inference_steps=req.steps,
            guidance_scale=req.guidance_scale,
            seed=req.seed,
            auto_optimize=req.auto_optimize,
            run_qa=req.run_qa,
            chat_history=chat_history,
            image_sources=req.image_sources
        )

        # Automatic chat session recording if session_id is provided
        if req.session_id:
            # Record user message
            user_msg = chat_store.add_message(
                session_id=req.session_id,
                role="user",
                content=req.prompt
            )

            # Record assistant generated image message
            file_path = result.get("file_path")
            filename = result.get("filename")
            image_url = f"/api/image/{filename}" if filename else None
            meta_record = {
                "prompt_used": result.get("prompt_used"),
                "generation_metadata": result.get("generation_metadata"),
                "qa_report": result.get("qa_report"),
                "latency_seconds": result.get("total_latency_seconds")
            }
            asst_msg = chat_store.add_message(
                session_id=req.session_id,
                role="assistant",
                content=f"Generated image: {req.prompt}",
                image_path=file_path,
                image_url=image_url,
                metadata=meta_record
            )
            chat_store.set_active_context(req.session_id, file_path)
            result["session_id"] = req.session_id
            result["user_message_id"] = user_msg["id"]
            result["assistant_message_id"] = asst_msg["id"]

        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")

@router.post("/api/edit")
async def edit_image(req: EditRequest):
    try:
        # Pre-flight OOM Fail-Safe check (reject if system RAM >= 90% to prevent laptop freeze)
        mem_ok, mem_reason = oom_guard.check_memory_preflight()
        if not mem_ok:
            raise HTTPException(status_code=503, detail=mem_reason)

        image_src = req.image_source
        chat_history = None
        if req.session_id:
            sess = chat_store.get_session(req.session_id)
            if sess:
                chat_history = sess.get("messages", [])
                # Context fallback from session's active image
                if (not image_src or not str(image_src).strip()) and (not req.image_sources or len(req.image_sources) == 0):
                    if sess.get("active_image_path"):
                        image_src = sess["active_image_path"]

        if (not image_src or not str(image_src).strip()) and (not req.image_sources or len(req.image_sources) == 0):
            raise HTTPException(
                status_code=400,
                detail="Invalid image request: image_source or image_sources is required (or session must have an active image context)."
            )

        edit_mode = req.edit_mode
        if (edit_mode == "transform" or not edit_mode) and req.prompt and req.prompt.strip():
            edit_mode = "ai_img2img"

        result = await orchestrator.orchestrate_image_edit(
            image_source=image_src,
            image_sources=req.image_sources,
            mask_source=req.mask_source,
            prompt=req.prompt,
            edit_mode=edit_mode,
            filter_preset=req.filter_preset,
            brightness=req.brightness,
            contrast=req.contrast,
            saturation=req.saturation,
            sharpness=req.sharpness,
            blur=req.blur,
            vignette=req.vignette,
            gamma=req.gamma,
            strength=req.strength,
            steps=req.steps,
            run_qa=req.run_qa,
            chat_history=chat_history
        )

        # Automatic chat session recording if session_id is provided
        if req.session_id:
            user_content = req.prompt or f"Apply filter '{req.filter_preset or req.edit_mode}'"
            user_msg = chat_store.add_message(
                session_id=req.session_id,
                role="user",
                content=user_content,
                image_path=image_src if not str(image_src).startswith("data:") else None,
                edit_parent_id=req.edit_parent_id
            )

            file_path = result.get("file_path")
            filename = result.get("filename")
            image_url = f"/api/image/{filename}" if filename else None
            asst_meta = {
                "edit_mode": req.edit_mode,
                "filter_preset": req.filter_preset,
                "strength": req.strength,
                "qa_report": result.get("qa_report"),
                "latency_seconds": result.get("total_latency_seconds")
            }
            asst_msg = chat_store.add_message(
                session_id=req.session_id,
                role="assistant",
                content=f"Edited image: {user_content}",
                image_path=file_path,
                image_url=image_url,
                edit_parent_id=user_msg["id"],
                metadata=asst_meta
            )
            chat_store.set_active_context(req.session_id, file_path)
            result["session_id"] = req.session_id
            result["user_message_id"] = user_msg["id"]
            result["assistant_message_id"] = asst_msg["id"]

        return result
    except HTTPException:
        raise
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"Image not found: {str(e)}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid image request: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image editing failed: {str(e)}")

@router.post("/api/qa")
def audit_image_quality(req: QARequest):
    try:
        img = load_image_from_path_or_b64(req.image_source)
        return qa_critic.analyze_image(img)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"Image not found: {str(e)}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid image request: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"QA audit failed: {str(e)}")

# =====================================================================
# Chat Sessions API Endpoints
# =====================================================================

@router.get("/api/sessions")
def get_chat_sessions():
    """Returns list of all chat sessions with summary (id, title, message_count, updated_at, preview_image)."""
    return chat_store.list_sessions()

@router.post("/api/sessions")
def create_chat_session(req: Optional[CreateSessionRequest] = None):
    """Creates a new chat session with optional title."""
    title = req.title if req else None
    return chat_store.create_session(title=title)

@router.get("/api/sessions/{session_id}")
def get_chat_session_detail(session_id: str):
    """Returns session details, active context, and message history."""
    session = chat_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    return session

@router.put("/api/sessions/{session_id}")
def update_chat_session(session_id: str, req: UpdateSessionRequest):
    """Update title or active image context."""
    session = chat_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    updated = chat_store.update_session(
        session_id=session_id,
        title=req.title,
        active_image_path=req.active_image_path
    )
    return updated

@router.delete("/api/sessions")
def clear_all_chat_sessions():
    """Clear all chat sessions and messages from database."""
    count = chat_store.clear_all_sessions()
    return {"success": True, "cleared_sessions_count": count}

@router.delete("/api/sessions/{session_id}")
def delete_chat_session(session_id: str):
    """Delete session and all its messages."""
    success = chat_store.delete_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    return {"success": True, "deleted_session_id": session_id}

@router.post("/api/sessions/{session_id}/messages")
def add_chat_message(session_id: str, req: AddMessageRequest):
    """Manually add a message to session."""
    session = chat_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    msg = chat_store.add_message(
        session_id=session_id,
        role=req.role,
        content=req.content,
        image_path=req.image_path,
        image_url=req.image_url,
        edit_parent_id=req.edit_parent_id,
        metadata=req.metadata
    )
    return msg

# =====================================================================
# Image Storage & Serving Endpoints
# =====================================================================

@router.get("/api/history")
def get_history():
    files = []
    for p in sorted(OUTPUTS_DIR.glob("*.png"), key=os.path.getmtime, reverse=True)[:30]:
        files.append({
            "filename": p.name,
            "url": f"/api/image/{p.name}",
            "size_kb": round(p.stat().st_size / 1024, 1),
            "created_at": p.stat().st_mtime
        })
    return {"images": files}

@router.get("/api/image/{filename}")
def get_image(filename: str):
    # Sanitize filename
    clean_name = Path(filename).name
    file_path = OUTPUTS_DIR / clean_name
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(path=file_path, media_type="image/png", headers={"Cache-Control": "public, max-age=86400"})

@router.post("/api/cache/clear")
@router.delete("/api/cache")
def clear_all_caches():
    """Clear all generated output images, disk caches (.cache, .qwen_cache, .stage_cache), ComfyUI caches, and in-memory caches."""
    import shutil
    from app.agents.generator import COMFY_DIR
    cleared_files = 0
    # 1. Clear output images
    for p in OUTPUTS_DIR.glob("*.png"):
        try:
            p.unlink()
            cleared_files += 1
        except Exception:
            pass

    # 2. Clear disk caches
    for cache_subdir in [".cache", ".qwen_cache", ".stage_cache"]:
        cdir = OUTPUTS_DIR / cache_subdir
        if cdir.exists():
            for item in list(cdir.glob("*")):
                try:
                    if item.is_file():
                        item.unlink()
                        cleared_files += 1
                    elif item.is_dir():
                        shutil.rmtree(item)
                        cleared_files += 1
                except Exception:
                    pass

    # 3. Clear root stage cache if any
    root_stage = OUTPUTS_DIR.parent / ".stage_cache"
    if root_stage.exists():
        for item in list(root_stage.glob("*")):
            try:
                if item.is_file():
                    item.unlink()
                    cleared_files += 1
                elif item.is_dir():
                    shutil.rmtree(item)
                    cleared_files += 1
            except Exception:
                pass

    # 4. Clear ComfyUI outputs and user inputs
    comfy_out = COMFY_DIR / "output"
    if comfy_out.exists():
        for item in list(comfy_out.glob("*")):
            if item.name == "_output_images_will_be_put_here":
                continue
            try:
                if item.is_file():
                    item.unlink()
                    cleared_files += 1
                elif item.is_dir():
                    shutil.rmtree(item)
                    cleared_files += 1
            except Exception:
                pass

    comfy_in = COMFY_DIR / "input"
    if comfy_in.exists():
        for item in list(comfy_in.glob("*")):
            if item.name == "example.png" or item.is_dir():
                continue
            try:
                if item.is_file():
                    item.unlink()
                    cleared_files += 1
            except Exception:
                pass

    # 5. Clear in-memory caches
    if hasattr(orchestrator, "clear_cache"):
        cleared_files += orchestrator.clear_cache()

    return {
        "success": True,
        "message": "All image outputs and caches cleared successfully",
        "cleared_files_count": cleared_files
    }

