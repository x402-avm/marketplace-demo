"""Diffusers-based Diffusion Backend for Gemini Nano Banana Image Gen.

Provides fast, high-quality inference using stabilityai/sd-turbo with AutoPipelineForText2Image
and AutoPipelineForImage2Image, sharing memory and weights across text2img and img2img tasks.
Supports GPU acceleration (CUDA) with graceful CPU fallback.
"""

import os
import math
import threading
from pathlib import Path
from typing import Optional, Union
from PIL import Image
import torch
from diffusers import AutoPipelineForText2Image, AutoPipelineForImage2Image

from app.config import OPTIMAL_THREADS
from app.utils.image_utils import load_image_from_path_or_b64


class DiffusersBackend:
    """Thread-safe, lazy-loading singleton backend for image generation with diffusers on GPU/CPU."""
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, model_id: Optional[str] = None):
        if getattr(self, "_initialized", False):
            return
        with self._lock:
            if getattr(self, "_initialized", False):
                return
            self.model_id = model_id or os.environ.get("IMAGE_MODEL_ID", "stabilityai/sd-turbo")
            # Prefer GPU (CUDA) when available, fallback to CPU
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            self.dtype = torch.float16 if self.device == "cuda" else torch.float32
            self._t2i_pipe = None
            self._i2i_pipe = None
            self._load_lock = threading.Lock()
            self._infer_lock = threading.Lock()
            self._initialized = True

    @property
    def name(self) -> str:
        return f"diffusers:{self.model_id}"

    def _ensure_loaded(self):
        if self._t2i_pipe is not None and self._i2i_pipe is not None:
            return
        with self._load_lock:
            if self._t2i_pipe is None:
                if self.device == "cpu":
                    torch.set_num_threads(OPTIMAL_THREADS)
                load_kwargs = {"torch_dtype": self.dtype}
                if self.device == "cuda":
                    load_kwargs["variant"] = "fp16"
                pipe = AutoPipelineForText2Image.from_pretrained(
                    self.model_id,
                    **load_kwargs
                )
                pipe.set_progress_bar_config(disable=True)
                pipe = pipe.to(self.device)
                self._t2i_pipe = pipe

            if self._i2i_pipe is None:
                i2i = AutoPipelineForImage2Image.from_pipe(self._t2i_pipe)
                i2i.set_progress_bar_config(disable=True)
                self._i2i_pipe = i2i

    def text2img(
        self,
        prompt: str,
        negative_prompt: str = "",
        width: int = 512,
        height: int = 512,
        steps: int = 4,
        guidance: float = 0.0,
        seed: Optional[int] = None
    ) -> Image.Image:
        """Generate an image from text prompt using diffusers."""
        self._ensure_loaded()
        is_sd_turbo = "sd-turbo" in self.model_id
        if is_sd_turbo:
            guidance = 0.0
            steps = max(1, min(int(steps), 4))
        else:
            steps = max(1, int(steps))

        w = min(768, max(64, (int(width) // 8) * 8))
        h = min(768, max(64, (int(height) // 8) * 8))

        generator = None
        if seed is not None and int(seed) >= 0:
            generator = torch.Generator(self.device).manual_seed(int(seed))

        kwargs = {
            "prompt": prompt,
            "width": w,
            "height": h,
            "num_inference_steps": steps,
            "guidance_scale": guidance,
        }
        if negative_prompt and guidance > 0:
            kwargs["negative_prompt"] = negative_prompt
        if generator is not None:
            kwargs["generator"] = generator

        with self._infer_lock:
            if self.device == "cpu":
                torch.set_num_threads(OPTIMAL_THREADS)
            out = self._t2i_pipe(**kwargs)
        return out.images[0]

    def img2img(
        self,
        image: Union[Image.Image, str, Path],
        prompt: str,
        strength: float = 0.6,
        steps: int = 4,
        seed: Optional[int] = None
    ) -> Image.Image:
        """Edit an image with prompt conditioning using diffusers."""
        self._ensure_loaded()
        if not isinstance(image, Image.Image):
            image = load_image_from_path_or_b64(str(image))
        init_img = image.convert("RGB")

        orig_w, orig_h = init_img.size
        scale = min(1.0, 768.0 / max(orig_w, orig_h))
        target_w = max(64, (int(orig_w * scale) // 8) * 8)
        target_h = max(64, (int(orig_h * scale) // 8) * 8)
        if (orig_w, orig_h) != (target_w, target_h):
            init_img = init_img.resize((target_w, target_h), Image.Resampling.LANCZOS)

        strength = float(strength)
        is_sd_turbo = "sd-turbo" in self.model_id
        if is_sd_turbo:
            guidance = 0.0
            min_steps = math.ceil(1.0 / max(0.01, strength))
            steps = max(int(steps), min_steps)
            steps = max(1, steps)
        else:
            guidance = 7.5
            steps = max(1, int(steps))

        generator = None
        if seed is not None and int(seed) >= 0:
            generator = torch.Generator(self.device).manual_seed(int(seed))

        kwargs = {
            "prompt": prompt,
            "image": init_img,
            "strength": strength,
            "num_inference_steps": steps,
            "guidance_scale": guidance,
        }
        if generator is not None:
            kwargs["generator"] = generator

        with self._infer_lock:
            if self.device == "cpu":
                torch.set_num_threads(OPTIMAL_THREADS)
            out = self._i2i_pipe(**kwargs)
        return out.images[0]
