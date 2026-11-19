import os
import uuid
import time
import math
from pathlib import Path
from typing import Dict, Any, Optional, List, Union, Tuple, Set
from PIL import Image

try:
    import numpy as np
except ImportError:
    np = None

try:
    import torch
except ImportError:
    torch = None

from app.config import OUTPUTS_DIR, STAGE_CACHE_DIR, ASPECT_RATIOS, FAST_TEST_MODE
from app.agents.prompt_optimizer import PromptOptimizerAgent
from app.agents.generator import InferenceAgent, QwenImageEngine
from app.agents.qa_critic import QualityAssuranceAgent, CritiqueResult
from app.image_ops.processor import ImageProcessor
from app.utils.hardware import get_system_hardware_profile
from app.utils.image_utils import image_to_base64, save_image_to_disk, load_image_from_path_or_b64, base64_to_image
from app.utils.oom_guard import oom_guard

# Ensure preflight_check method exists on oom_guard singleton
if not hasattr(oom_guard, "preflight_check"):
    oom_guard.preflight_check = oom_guard.check_memory_preflight


class AgentOrchestrator:
    """Multi-Agent Orchestrator: Combines Prompt Engineer, Generator, QA Critic, and CV Processor
    with active OOM Guard pre-flight checks and guaranteed intermediate stage cache cleanup.
    """

    def __init__(self, generator: Optional[InferenceAgent] = None):
        self.optimizer = PromptOptimizerAgent()
        self.qa_critic = QualityAssuranceAgent()
        self.generator = generator or InferenceAgent()
        self.processor = ImageProcessor()
        self.stage_cache_dir = STAGE_CACHE_DIR
        self.stage_cache_dir.mkdir(parents=True, exist_ok=True)

    def _process_thought_image(
        self,
        gen_meta: Optional[Dict[str, Any]],
        job_id: Optional[str] = None
    ) -> Tuple[Optional[str], Optional[str]]:
        """Extract, persist, and encode intermediate draft image (thought_image).
        Returns (thought_image_url, thought_image_base64).
        If no draft image or metadata is present, returns (None, None).
        """
        if not isinstance(gen_meta, dict):
            return None, None

        thought_url = gen_meta.get("thought_image_url")
        thought_b64 = gen_meta.get("thought_image_base64")

        tid = job_id or uuid.uuid4().hex[:10]
        draft_obj = gen_meta.get("thought_image") or gen_meta.get("draft_image")

        res_url: Optional[str] = None
        res_b64: Optional[str] = None

        if thought_url and thought_b64:
            res_url, res_b64 = thought_url, thought_b64
        elif isinstance(draft_obj, Image.Image):
            try:
                thought_filename = f"thought_{tid}.png"
                save_image_to_disk(draft_obj, OUTPUTS_DIR, thought_filename)
                res_url = f"/api/image/{thought_filename}"
                res_b64 = image_to_base64(draft_obj)
            except Exception:
                res_url, res_b64 = None, None
        elif isinstance(draft_obj, str) and draft_obj.strip():
            if draft_obj.startswith("data:image/"):
                res_b64 = draft_obj
                try:
                    loaded = base64_to_image(draft_obj)
                    thought_filename = f"thought_{tid}.png"
                    save_image_to_disk(loaded, OUTPUTS_DIR, thought_filename)
                    res_url = f"/api/image/{thought_filename}"
                except Exception:
                    res_url, res_b64 = None, draft_obj
            elif draft_obj.startswith("/api/image/"):
                res_url = draft_obj
                res_b64 = None
            else:
                try:
                    loaded = load_image_from_path_or_b64(draft_obj)
                    thought_filename = f"thought_{tid}.png"
                    save_image_to_disk(loaded, OUTPUTS_DIR, thought_filename)
                    res_url = f"/api/image/{thought_filename}"
                    res_b64 = image_to_base64(loaded)
                except Exception:
                    res_url, res_b64 = None, None
        elif thought_url and not thought_b64:
            res_url = thought_url
            try:
                loaded = load_image_from_path_or_b64(thought_url)
                res_b64 = image_to_base64(loaded)
            except Exception:
                pass
        elif thought_b64 and not thought_url:
            res_b64 = thought_b64
            try:
                loaded = base64_to_image(thought_b64)
                thought_filename = f"thought_{tid}.png"
                save_image_to_disk(loaded, OUTPUTS_DIR, thought_filename)
                res_url = f"/api/image/{thought_filename}"
            except Exception:
                pass

        # In-place metadata sanitization: Replace non-serializable objects with JSON primitives
        if "thought_image" in gen_meta:
            gen_meta["thought_image"] = res_url
        if "draft_image" in gen_meta:
            gen_meta["draft_image"] = res_url
        if res_url is not None:
            gen_meta["thought_image_url"] = res_url
        if res_b64 is not None:
            gen_meta["thought_image_base64"] = res_b64

        return res_url, res_b64

    async def orchestrate_text_to_image(
        self,
        prompt: str,
        style: str = "photorealistic",
        negative_prompt: str = "",
        aspect_ratio: str = "1:1",
        num_inference_steps: int = 15,
        guidance_scale: float = 7.5,
        seed: Optional[int] = None,
        auto_optimize: bool = True,
        run_qa: bool = True,
        chat_history: Optional[list] = None,
        image_sources: Optional[list] = None,
        strength: float = 0.65,
        resolution: Optional[int] = None
    ) -> Dict[str, Any]:
        """Execute full end-to-end multi-agent Text-to-Image pipeline with multi-turn context,
        resolution scaling up to 1024, user strength parameterization, and active OOM Guard checks.
        """
        # 0. Active OOM Guard pre-flight check before initiating generation
        safe, reason = oom_guard.preflight_check()
        if not safe:
            raise RuntimeError(f"OOM Guard Pre-flight Rejection: {reason}")

        start_time = time.time()
        job_id = uuid.uuid4().hex[:10]
        audit_log = []
        gen_meta = {}

        # Resolution scaling resolution parameterization (up to 1024)
        effective_aspect_ratio = aspect_ratio
        if resolution:
            clamped_res = min(1024, max(64, int(resolution)))
            candidate_1024 = f"{aspect_ratio}_{clamped_res}"
            if candidate_1024 in ASPECT_RATIOS:
                effective_aspect_ratio = candidate_1024
            elif clamped_res == 1024 and aspect_ratio == "1:1":
                effective_aspect_ratio = "1024x1024"
            elif f"{aspect_ratio}_1024" in ASPECT_RATIOS and clamped_res >= 768:
                effective_aspect_ratio = f"{aspect_ratio}_1024"

        try:
            # 1. Agent 1: AI Prompt Engineer (with conversational history context)
            cot_start = time.perf_counter()
            if auto_optimize:
                opt_result = self.optimizer.optimize_with_context(
                    raw_prompt=prompt,
                    chat_history=chat_history,
                    style=style,
                    negative_prompt=negative_prompt,
                    custom_aspect_ratio=effective_aspect_ratio
                )
                final_prompt = opt_result["optimized_prompt"]
                final_negative = opt_result["negative_prompt"]
                effective_aspect_ratio = opt_result["recommended_aspect_ratio"]
                cot_duration = time.perf_counter() - cot_start
                cot_latency_sec = round(cot_duration, 4)
                cot_latency_ms = round(cot_duration * 1000.0, 2)
                cot_reasoning = opt_result.get("cot_reasoning", {})
                thinking_trace = cot_reasoning.get("thinking_trace") or opt_result.get("thinking_trace", [])
                if not thinking_trace:
                    thinking_trace = [
                        f"1. Decomposed user prompt into core scene subjects: '{prompt}'.",
                        f"2. Applied '{style}' aesthetic style preset and modifier constraints.",
                        f"3. Enforced attribute-entity binding to prevent color/modifier bleeding.",
                        f"4. Synthesized cohesive prompt for diffusion backbone."
                    ]
                audit_log.append({
                    "agent": "PromptOptimizerAgent",
                    "action": "Enriched user prompt with style aesthetics and multi-turn conversational context",
                    "optimized_prompt": final_prompt,
                    "negative_prompt": final_negative,
                    "had_context": opt_result.get("had_context", False),
                    "cot_latency_ms": cot_latency_ms
                })
            else:
                cot_duration = time.perf_counter() - cot_start
                cot_latency_sec = round(cot_duration, 4)
                cot_latency_ms = round(cot_duration * 1000.0, 2)
                final_prompt = prompt
                final_negative = negative_prompt
                thinking_trace = [
                    f"1. Passthrough mode: user prompt '{prompt}' used verbatim.",
                    f"2. Automated prompt expansion bypassed per user configuration.",
                    f"3. Direct dispatch to image synthesis backbone."
                ]
                cot_reasoning = {
                    "mode": "manual",
                    "thinking_trace": thinking_trace,
                    "raw_prompt": prompt,
                    "synthesized_prompt": prompt
                }
                audit_log.append({
                    "agent": "PromptOptimizerAgent",
                    "action": "Bypassed prompt expansion (manual mode)",
                    "prompt": final_prompt,
                    "cot_latency_ms": cot_latency_ms
                })

            # Apply resolution parameterization (up to 1024)
            target_aspect_ratio = effective_aspect_ratio
            if resolution:
                clamped_res = min(1024, max(64, int(resolution)))
                candidate_1024 = f"{effective_aspect_ratio}_{clamped_res}"
                if candidate_1024 in ASPECT_RATIOS:
                    target_aspect_ratio = candidate_1024
                elif clamped_res == 1024 and effective_aspect_ratio == "1:1":
                    target_aspect_ratio = "1024x1024"
                elif f"{effective_aspect_ratio}_1024" in ASPECT_RATIOS and clamped_res >= 768:
                    target_aspect_ratio = f"{effective_aspect_ratio}_1024"
                elif clamped_res == 1024:
                    target_aspect_ratio = "1024x1024"

            # 2. Agent 2: Inference Engine (with optional multi-image conditioning)
            if image_sources and len(image_sources) > 0:
                loaded_imgs = [load_image_from_path_or_b64(src) for src in image_sources if src]
                if len(loaded_imgs) > 0:
                    image, gen_meta = await self.generator.generate_image_to_image(
                        init_image=loaded_imgs,
                        prompt=final_prompt,
                        negative_prompt=final_negative,
                        strength=strength,
                        num_inference_steps=num_inference_steps
                    )
                    gen_meta = gen_meta if isinstance(gen_meta, dict) else {}
                    audit_log.append({
                        "agent": "InferenceAgent",
                        "action": f"Executed native multi-image conditioned synthesis on CPU ({len(loaded_imgs)} reference images) with strength {strength}",
                        "latency_seconds": gen_meta.get("latency_seconds") or 0.0,
                        "resolution": f"{gen_meta.get('width') or 512}x{gen_meta.get('height') or 512}"
                    })
                else:
                    image, gen_meta = await self.generator.generate_text_to_image(
                        prompt=final_prompt,
                        negative_prompt=final_negative,
                        aspect_ratio=target_aspect_ratio,
                        num_inference_steps=num_inference_steps,
                        guidance_scale=guidance_scale,
                        seed=seed
                    )
                    gen_meta = gen_meta if isinstance(gen_meta, dict) else {}
                    audit_log.append({
                        "agent": "InferenceAgent",
                        "action": f"Executed inference on CPU ({gen_meta.get('engine') or 'qwen2.1'})",
                        "latency_seconds": gen_meta.get("latency_seconds") or 0.0,
                        "resolution": f"{gen_meta.get('width') or 512}x{gen_meta.get('height') or 512}"
                    })
            else:
                image, gen_meta = await self.generator.generate_text_to_image(
                    prompt=final_prompt,
                    negative_prompt=final_negative,
                    aspect_ratio=target_aspect_ratio,
                    num_inference_steps=num_inference_steps,
                    guidance_scale=guidance_scale,
                    seed=seed
                )
                gen_meta = gen_meta if isinstance(gen_meta, dict) else {}
                audit_log.append({
                    "agent": "InferenceAgent",
                    "action": f"Executed inference on CPU ({gen_meta.get('engine') or 'qwen2.1'})",
                    "latency_seconds": gen_meta.get("latency_seconds") or 0.0,
                    "resolution": f"{gen_meta.get('width') or 512}x{gen_meta.get('height') or 512}"
                })

            # Process intermediate visual scratchpad preview (thought_image)
            thought_image_url, thought_image_base64 = self._process_thought_image(gen_meta, job_id=job_id)
            if thought_image_url:
                gen_meta["thought_image_url"] = thought_image_url
                gen_meta["thought_image_base64"] = thought_image_base64
                audit_log.append({
                    "agent": "InferenceAgent",
                    "action": f"Captured intermediate visual scratchpad preview ({thought_image_url})",
                    "thought_image_url": thought_image_url
                })
            if isinstance(gen_meta, dict):
                if "thought_image" in gen_meta:
                    gen_meta["thought_image"] = thought_image_url
                if "draft_image" in gen_meta:
                    gen_meta["draft_image"] = thought_image_url

            # 3. Agent 3: Quality Assurance & Critic
            qa_report = {}
            raw_stage_metrics = gen_meta.get("stage_metrics") if isinstance(gen_meta, dict) else None
            if isinstance(raw_stage_metrics, dict):
                stage_metrics = dict(raw_stage_metrics)
            else:
                stage_metrics = {}

            stage_metrics["cot_reasoning_seconds"] = cot_latency_sec
            stage_metrics["cot_reasoning_ms"] = cot_latency_ms

            latencies = stage_metrics.get("latencies")
            if not isinstance(latencies, dict):
                latencies = {}
            else:
                latencies = dict(latencies)
            latencies["cot_reasoning_seconds"] = cot_latency_sec
            latencies["cot_reasoning_ms"] = cot_latency_ms

            # Synchronize thought_image draft latencies if draft pass executed
            draft_sec = (
                latencies.get("thought_image_draft_seconds")
                or stage_metrics.get("thought_image_draft_seconds")
                or (gen_meta.get("thought_image_draft_seconds") if isinstance(gen_meta, dict) else None)
            )
            draft_ms = (
                latencies.get("thought_image_draft_ms")
                or stage_metrics.get("thought_image_draft_ms")
                or (gen_meta.get("thought_image_draft_ms") if isinstance(gen_meta, dict) else None)
            )
            if draft_sec is not None and draft_ms is None:
                draft_ms = round(float(draft_sec) * 1000.0, 2)
            elif draft_ms is not None and draft_sec is None:
                draft_sec = round(float(draft_ms) / 1000.0, 4)
            elif draft_sec is None and draft_ms is None and thought_image_url is not None:
                draft_sec = 0.0
                draft_ms = 0.0

            if draft_sec is not None and draft_ms is not None:
                latencies["thought_image_draft_seconds"] = float(draft_sec)
                latencies["thought_image_draft_ms"] = float(draft_ms)
                stage_metrics["thought_image_draft_seconds"] = float(draft_sec)
                stage_metrics["thought_image_draft_ms"] = float(draft_ms)

            stage_metrics["latencies"] = latencies
            if run_qa:
                qa_report = self.qa_critic.analyze_image(image, prompt=final_prompt, stage_metrics=stage_metrics)
                audit_log.append({
                    "agent": "QualityAssuranceAgent",
                    "action": f"Evaluated image quality: Score {qa_report['quality_score']}/100 ({qa_report['status']})",
                    "grade": qa_report["grade"],
                    "passed": qa_report["passed_qa"]
                })

            # 4. Storage & Serialization
            filename = f"gen_{job_id}.png"
            file_path = save_image_to_disk(image, OUTPUTS_DIR, filename)
            b64_url = image_to_base64(image)

            total_time = round(time.time() - start_time, 3)
            hw_profile = get_system_hardware_profile()
            backend_name = QwenImageEngine.get_backend_name()

            res_payload = {
                "success": True,
                "filename": filename,
                "file_path": str(file_path),
                "backend": backend_name,
                "image_url": f"/api/image/{filename}",
                "image_base64": b64_url,
                "thought_image_url": thought_image_url,
                "thought_image_base64": thought_image_base64,
                "thinking_trace": thinking_trace,
                "cot_reasoning": cot_reasoning,
                "prompt_used": final_prompt,
                "negative_prompt_used": final_negative,
                "generation_metadata": gen_meta,
                "stage_metrics": stage_metrics,
                "qa_report": qa_report,
                "audit_log": audit_log,
                "total_latency_seconds": total_time,
                "hardware": {
                    "cpu_model": hw_profile["cpu_model"],
                    "torch_threads": hw_profile["torch_threads"],
                    "dgpu_isolated": hw_profile["dgpu_isolated"],
                    "device": hw_profile["device"]
                }
            }
            return self._sanitize_for_json(res_payload)
        finally:
            # Guarantee intermediate stage cache files are cleaned up
            self._cleanup_transient_stage_cache()

    async def orchestrate_image_generation(self, *args, **kwargs) -> Dict[str, Any]:
        """Alias for orchestrate_text_to_image providing unified central pipeline staging interface."""
        return await self.orchestrate_text_to_image(*args, **kwargs)

    async def orchestrate_image_edit(
        self,
        image_source: Optional[str] = None,
        image_sources: Optional[list] = None,
        mask_source: Optional[str] = None,
        prompt: Optional[str] = None,
        edit_mode: str = "transform",  # "transform" or "ai_img2img"
        filter_preset: Optional[str] = None,
        brightness: float = 1.0,
        contrast: float = 1.0,
        saturation: float = 1.0,
        sharpness: float = 1.0,
        blur: float = 0.0,
        vignette: float = 0.0,
        gamma: float = 1.0,
        strength: float = 0.65,
        steps: int = 15,
        run_qa: bool = True,
        chat_history: Optional[list] = None,
        resolution: Optional[int] = None
    ) -> Dict[str, Any]:
        """Execute full image editing pipeline with multi-image composition, conversational context,
        user strength parameterization, high-resolution scaling up to 1024, and active OOM Guard checks.
        """
        # 0. Active OOM Guard pre-flight check before initiating image editing
        safe, reason = oom_guard.preflight_check()
        if not safe:
            raise RuntimeError(f"OOM Guard Pre-flight Rejection: {reason}")

        start_time = time.time()
        job_id = uuid.uuid4().hex[:10]
        audit_log = []
        gen_meta = {}

        # Determine all input images (multi-image support)
        all_sources = []
        if image_sources:
            all_sources.extend([s for s in image_sources if s])
        if image_source and image_source not in all_sources:
            all_sources.insert(0, image_source)

        if not all_sources:
            raise ValueError("No valid image source provided for editing")

        loaded_images = [load_image_from_path_or_b64(src) for src in all_sources]

        # Resolution scaling if requested (up to 1024)
        if resolution:
            max_target = min(1024, max(64, int(resolution)))
            scaled_images = []
            for img in loaded_images:
                w, h = img.size
                max_dim = max(w, h)
                if max_dim > max_target:
                    scale = float(max_target) / float(max_dim)
                    tw = max(64, int((w * scale) // 16) * 16)
                    th = max(64, int((h * scale) // 16) * 16)
                    scaled_images.append(img.resize((tw, th), Image.Resampling.LANCZOS))
                else:
                    scaled_images.append(img)
            loaded_images = scaled_images

        primary_input_image = loaded_images[0]

        if len(loaded_images) > 1:
            current_image = loaded_images
            audit_log.append({
                "agent": "InferenceAgent",
                "action": f"Conditioning on {len(loaded_images)} discrete reference images with native vision encoding (no blending)"
            })
        else:
            current_image = loaded_images[0]

        try:
            # 1. AI Diffusion Edit (with multi-turn chat history context)
            effective_mode = edit_mode
            if (effective_mode == "transform" or not effective_mode) and prompt and str(prompt).strip():
                effective_mode = "ai_img2img"

            cot_start = time.perf_counter()
            cot_latency_sec = 0.0
            cot_latency_ms = 0.0
            thinking_trace = []
            cot_reasoning = {}
            final_prompt = None

            if effective_mode == "ai_img2img" and prompt and prompt.strip():
                num_refs = len(current_image) if isinstance(current_image, list) else 1
                ref_summary = None
                if chat_history and len(chat_history) > 0:
                    last_user_msgs = [m.get("content", "") for m in chat_history if isinstance(m, dict) and m.get("role") == "user"]
                    if last_user_msgs:
                        ref_summary = f"Prior context: {last_user_msgs[-1]}"

                if hasattr(self.optimizer, "optimize_edit_with_reasoning"):
                    edit_res = self.optimizer.optimize_edit_with_reasoning(
                        instruction=prompt,
                        parent_prompt=ref_summary,
                        image_context=f"{num_refs} reference image(s)" if num_refs > 1 else "single reference image",
                        chat_history=chat_history,
                        num_images=num_refs
                    )
                    final_prompt = edit_res["optimized_prompt"]
                    final_negative = edit_res.get("negative_prompt", "distorted anatomy, deformed limbs, blurry focus, artificial skin texture, low contrast, visual artifacts")
                    thinking_trace = edit_res.get("thinking_trace", [])
                    cot_reasoning = edit_res.get("cot_reasoning", edit_res)
                else:
                    final_prompt = self.optimizer.optimize_edit_instruction(
                        instruction=prompt,
                        reference_summary=ref_summary,
                        num_images=num_refs
                    )
                    final_negative = "distorted anatomy, deformed limbs, blurry focus, artificial skin texture, low contrast, visual artifacts"
                    mode_label = "multi-image composition" if num_refs > 1 else "single-image edit"
                    thinking_trace = [
                        f"1. Decomposed edit instruction into operational deltas: '{prompt}'.",
                        f"2. Resolved context and reference bindings ({ref_summary or 'initial input image'}).",
                        f"3. Established identity and attribute preservation constraints for {mode_label}.",
                        f"4. Synthesized Qwen-VL ChatML prompt targeting requested modifications."
                    ]
                    cot_reasoning = {
                        "mode": "i2i_multi" if num_refs > 1 else "i2i_single",
                        "instruction": prompt,
                        "reference_summary": ref_summary,
                        "num_images": num_refs,
                        "thinking_trace": thinking_trace
                    }

                cot_duration = time.perf_counter() - cot_start
                cot_latency_sec = round(cot_duration, 4)
                cot_latency_ms = round(cot_duration * 1000.0, 2)
                had_ctx = bool(ref_summary)

                effective_steps = steps if (steps is not None and steps > 0) else 15
                current_image, gen_meta = await self.generator.generate_image_to_image(
                    init_image=current_image,
                    prompt=final_prompt,
                    negative_prompt=final_negative,
                    strength=strength,
                    num_inference_steps=effective_steps,
                    guidance_scale=4.0
                )
                gen_meta = gen_meta if isinstance(gen_meta, dict) else {}
                thought_image_url, thought_image_base64 = self._process_thought_image(gen_meta, job_id=job_id)
                if thought_image_url:
                    gen_meta["thought_image_url"] = thought_image_url
                    gen_meta["thought_image_base64"] = thought_image_base64
                    audit_log.append({
                        "agent": "InferenceAgent",
                        "action": f"Captured intermediate visual scratchpad preview ({thought_image_url})",
                        "thought_image_url": thought_image_url
                    })
                if isinstance(gen_meta, dict):
                    if "thought_image" in gen_meta:
                        gen_meta["thought_image"] = thought_image_url
                    if "draft_image" in gen_meta:
                        gen_meta["draft_image"] = thought_image_url
                audit_log.append({
                    "agent": "InferenceAgent",
                    "action": f"Applied in-context AI Img2Img transformation with strength {strength}",
                    "prompt": final_prompt,
                    "had_context": had_ctx,
                    "cot_latency_ms": cot_latency_ms
                })
            elif isinstance(current_image, list):
                thought_image_url = None
                thought_image_base64 = None
                # If not using AI diffusion edit, default to primary image for subsequent manual filters
                current_image = current_image[0]
                cot_duration = time.perf_counter() - cot_start
                cot_latency_sec = round(cot_duration, 4)
                cot_latency_ms = round(cot_duration * 1000.0, 2)
                thinking_trace = [
                    f"1. Evaluated multi-image reference inputs ({len(loaded_images)} images).",
                    "2. Selected primary reference image for transformation.",
                    "3. Prepared image canvas for downstream image operations."
                ]
                cot_reasoning = {
                    "mode": "transform",
                    "num_images": len(loaded_images),
                    "thinking_trace": thinking_trace
                }
            else:
                thought_image_url = None
                thought_image_base64 = None
                cot_duration = time.perf_counter() - cot_start
                cot_latency_sec = round(cot_duration, 4)
                cot_latency_ms = round(cot_duration * 1000.0, 2)
                thinking_trace = [
                    f"1. Evaluated parametric and aesthetic preset adjustments: preset='{filter_preset or 'none'}'.",
                    "2. Computed tone curve, saturation, and contrast transforms.",
                    "3. Rendered direct pixel adjustments without diffusion inference."
                ]
                cot_reasoning = {
                    "mode": "transform",
                    "filter_preset": filter_preset,
                    "thinking_trace": thinking_trace
                }

            # 2. Preset Filter Application
            if filter_preset and filter_preset.lower() != "none":
                current_image = self.processor.apply_preset(current_image, filter_preset)
                audit_log.append({
                    "agent": "ImageProcessor",
                    "action": f"Applied aesthetic preset filter: '{filter_preset}'"
                })

            # 3. Fine-tuning Parametric Adjustments
            if any(v != 1.0 for v in [brightness, contrast, saturation, sharpness, gamma]) or blur > 0.0 or vignette > 0.0:
                current_image = self.processor.adjust_image(
                    current_image,
                    brightness=brightness,
                    contrast=contrast,
                    saturation=saturation,
                    sharpness=sharpness,
                    blur=blur,
                    vignette=vignette,
                    gamma=gamma
                )
                audit_log.append({
                    "agent": "ImageProcessor",
                    "action": "Applied parametric color, contrast, and tone adjustments"
                })

            # 4. Inpainting Mask Compositing (if mask_source is supplied)
            if mask_source and mask_source.strip():
                try:
                    mask_image = load_image_from_path_or_b64(mask_source).convert("L")
                    if mask_image.size != current_image.size:
                        mask_image = mask_image.resize(current_image.size, Image.Resampling.NEAREST)
                    # Composite: current_image (edited) where mask is white (255), primary_input_image (original) where mask is black (0)
                    current_image = Image.composite(current_image, primary_input_image, mask_image)
                    audit_log.append({
                        "agent": "InpaintingCompositor",
                        "action": "Composited edits onto user-specified canvas mask"
                    })
                except Exception as e:
                    audit_log.append({
                        "agent": "InpaintingCompositor",
                        "action": f"Warning: Failed to apply inpainting mask ({str(e)}), applied globally"
                    })

            # 5. QA Audit
            qa_report = {}
            raw_stage_metrics = gen_meta.get("stage_metrics") if (effective_mode == "ai_img2img" and isinstance(gen_meta, dict)) else None
            if isinstance(raw_stage_metrics, dict):
                stage_metrics = dict(raw_stage_metrics)
            else:
                stage_metrics = {}

            # Always populate CoT reasoning latency at top-level
            stage_metrics["cot_reasoning_seconds"] = cot_latency_sec
            stage_metrics["cot_reasoning_ms"] = cot_latency_ms

            # Always guarantee nested 'latencies' dict is present and populated
            latencies = stage_metrics.get("latencies")
            if not isinstance(latencies, dict):
                latencies = {}
            else:
                latencies = dict(latencies)
            latencies["cot_reasoning_seconds"] = cot_latency_sec
            latencies["cot_reasoning_ms"] = cot_latency_ms

            # Synchronize thought_image draft latencies if draft pass executed
            if effective_mode == "ai_img2img":
                draft_sec = (
                    latencies.get("thought_image_draft_seconds")
                    or stage_metrics.get("thought_image_draft_seconds")
                    or (gen_meta.get("thought_image_draft_seconds") if isinstance(gen_meta, dict) else None)
                )
                draft_ms = (
                    latencies.get("thought_image_draft_ms")
                    or stage_metrics.get("thought_image_draft_ms")
                    or (gen_meta.get("thought_image_draft_ms") if isinstance(gen_meta, dict) else None)
                )
                if draft_sec is not None and draft_ms is None:
                    draft_ms = round(float(draft_sec) * 1000.0, 2)
                elif draft_ms is not None and draft_sec is None:
                    draft_sec = round(float(draft_ms) / 1000.0, 4)
                elif draft_sec is None and draft_ms is None and thought_image_url is not None:
                    draft_sec = 0.0
                    draft_ms = 0.0

                if draft_sec is not None and draft_ms is not None:
                    latencies["thought_image_draft_seconds"] = float(draft_sec)
                    latencies["thought_image_draft_ms"] = float(draft_ms)
                    stage_metrics["thought_image_draft_seconds"] = float(draft_sec)
                    stage_metrics["thought_image_draft_ms"] = float(draft_ms)

            stage_metrics["latencies"] = latencies
            if run_qa:
                qa_report = self.qa_critic.analyze_image(current_image, prompt=prompt, stage_metrics=stage_metrics)
                audit_log.append({
                    "agent": "QualityAssuranceAgent",
                    "action": f"Evaluated edited image: Quality Score {qa_report['quality_score']}/100"
                })

            filename = f"edit_{job_id}.png"
            file_path = save_image_to_disk(current_image, OUTPUTS_DIR, filename)
            b64_url = image_to_base64(current_image)
            total_time = round(time.time() - start_time, 3)
            hw_profile = get_system_hardware_profile()
            backend_name = QwenImageEngine.get_backend_name()

            res_payload = {
                "success": True,
                "filename": filename,
                "file_path": str(file_path),
                "backend": backend_name,
                "image_url": f"/api/image/{filename}",
                "image_base64": b64_url,
                "thought_image_url": thought_image_url,
                "thought_image_base64": thought_image_base64,
                "thinking_trace": thinking_trace,
                "cot_reasoning": cot_reasoning,
                "prompt_used": prompt if effective_mode == "ai_img2img" else None,
                "optimized_prompt": final_prompt if effective_mode == "ai_img2img" else None,
                "preservation_notes": cot_reasoning.get("preservation_notes") if isinstance(cot_reasoning, dict) else None,
                "original_resolution": f"{primary_input_image.width}x{primary_input_image.height}",
                "edited_resolution": f"{current_image.width}x{current_image.height}",
                "generation_metadata": gen_meta if effective_mode == "ai_img2img" else {},
                "stage_metrics": stage_metrics,
                "qa_report": qa_report,
                "audit_log": audit_log,
                "total_latency_seconds": total_time,
                "hardware": {
                    "cpu_model": hw_profile["cpu_model"],
                    "dgpu_isolated": hw_profile["dgpu_isolated"],
                    "device": "cpu"
                }
            }
            return self._sanitize_for_json(res_payload)
        finally:
            # Guarantee intermediate stage cache files are cleaned up
            self._cleanup_transient_stage_cache()

    @staticmethod
    def _sanitize_for_json(obj: Any, seen: Optional[Set[int]] = None) -> Any:
        """Recursively sanitize data structure into strictly JSON-serializable primitives
        with cycle detection, NumPy/PyTorch scalar and tensor conversions, and NaN/Inf protection.
        """
        if seen is None:
            seen = set()

        # Fast-path for common primitives
        if obj is None or isinstance(obj, (bool, int, str)):
            return obj

        # Standard Python float (handling NaN and Inf)
        if isinstance(obj, float):
            return 0.0 if (math.isnan(obj) or math.isinf(obj)) else obj

        # NumPy scalars and arrays
        if np is not None:
            if isinstance(obj, np.integer):
                return int(obj)
            if isinstance(obj, np.floating):
                val = float(obj)
                return 0.0 if (math.isnan(val) or math.isinf(val)) else val
            if isinstance(obj, np.bool_):
                return bool(obj)
            if isinstance(obj, np.ndarray):
                return AgentOrchestrator._sanitize_for_json(obj.tolist(), seen)

        # PyTorch tensors
        if torch is not None and isinstance(obj, torch.Tensor):
            detached = obj.detach().cpu()
            if detached.ndim == 0:
                val = detached.item()
                if isinstance(val, float):
                    return 0.0 if (math.isnan(val) or math.isinf(val)) else val
                return val
            return AgentOrchestrator._sanitize_for_json(detached.tolist(), seen)

        # Path objects
        if isinstance(obj, Path):
            return str(obj)

        # PIL Images are non-serializable binary buffers
        if isinstance(obj, Image.Image):
            return None

        # Compound containers with cycle detection
        if isinstance(obj, (dict, list, tuple, set)):
            obj_id = id(obj)
            if obj_id in seen:
                return "[Circular Reference]"
            seen.add(obj_id)
            try:
                if isinstance(obj, dict):
                    return {str(k): AgentOrchestrator._sanitize_for_json(v, seen) for k, v in obj.items()}
                return [AgentOrchestrator._sanitize_for_json(v, seen) for v in obj]
            finally:
                seen.remove(obj_id)

        # Fallback string representation
        return str(obj)

    def _cleanup_transient_stage_cache(self) -> int:
        """Unlink any lingering intermediate stage tensor cache files (*.pt) in STAGE_CACHE_DIR."""
        cleaned = 0
        try:
            if self.stage_cache_dir.exists():
                for f in self.stage_cache_dir.glob("*.pt"):
                    try:
                        f.unlink()
                        cleaned += 1
                    except Exception:
                        pass
        except Exception:
            pass
        return cleaned

    def clear_cache(self) -> int:
        """Clear intermediate stage tensor caches and free engine backend memory."""
        cleared = 0
        if hasattr(self, "generator") and hasattr(self.generator, "clear_cache"):
            cleared += self.generator.clear_cache()
        cleared += self._cleanup_transient_stage_cache()
        return cleared
