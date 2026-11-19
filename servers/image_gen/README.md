# Gemini Nano Banana — Image Generation & AI Editing System

Production-ready local AI image generation and editing engine engineered specifically for **AMD Ryzen AI 9 HX 370 (Zen 5, 24 threads)** with **complete discrete GPU (NVIDIA RTX 4070) isolation**.

ComfyUI dependencies have been completely eliminated in favor of a native, high-performance Python multi-agent pipeline and modern Gemini Nano Banana web interface.

---

## 🌟 Key Features

1. **Strict Discrete GPU Isolation (CPU-Only)**
   - Hardcoded hardware isolation (`CUDA_VISIBLE_DEVICES=""`).
   - PyTorch actively tuned for AMD Ryzen AI 9 HX 370 with 24 OpenMP threads and AVX-512 instruction support.
   - The NVIDIA GeForce RTX 4070 mobile GPU is strictly locked and completely unused.

2. **Gemini Nano Banana Web Interface (`http://localhost:10000`)**
   - **Text to Image**: Prompt input with 1-click **AI Prompt Engineer**, style presets (Photorealistic, Cinematic 8K, Anime, Studio Portrait, Cyberpunk, Fantasy Oil, Analog 35mm), aspect ratio presets (1:1, 16:9, 9:16, 4:3, 3:2), and live progress indicators.
   - **Interactive Split Comparison Editor**: Draggable Before/After split slider to compare original vs edited images in real-time. Supports AI prompt-guided synthesis and instant CPU filters (Cinematic, HDR, Portrait Bokeh, Noir, Golden Hour, Neon Cyber, Vintage, Pencil Sketch, Edge Detect).
   - **Multi-Agent Orchestrator**: Real-time visual feedback and interactive prompt playground.
   - **System Telemetry**: Live CPU thread usage, memory statistics, and dGPU isolation audit.

3. **Multi-Agent Orchestration Architecture**
   - **Agent 1 (AI Prompt Engineer)**: Semantically enriches user prompts, selects aesthetic descriptors, and crafts negative prompts to prevent visual defects.
   - **Agent 2 (CPU Inference Engine)**: Executes async CPU diffusion synthesis and image-to-image transformations using DPMSolver++ fast scheduling and procedural synthesis fallback.
   - **Agent 3 (QA Critic Agent)**: Mathematically audits output images for Laplacian sharpness variance, RMS contrast, highlight/shadow clipping percentages, and produces a 0-100 quality score with actionable feedback.
   - **Agent 4 (Hardware Guardian)**: Continuous monitoring ensuring the discrete GPU remains unallocated.

4. **Port Allocation (Strictly in 10000-10100)**
   - Central Backend & Web UI: **Port 10000**
   - FastMCP Server 1: **Port 10002**
   - FastMCP Server 2: **Port 10003**
   - FastMCP Server 3: **Port 10004**

---

## 🚀 Quick Start

### 1. Activate Environment
```bash
cd servers/image_gen
source venv/bin/activate
```

### 2. Launch Central Runtime Server & Web UI (Port 10000)
```bash
python runtime_server.py
```
Open your browser at **http://localhost:10000** to interact with the Gemini Nano Banana interface.

### 3. Launch FastMCP Services (Ports 10002, 10003, 10004)
In separate terminals:
```bash
python mcp_server_1.py
```
```bash
python mcp_server_2.py
```

### 4. Run Automated Client Test
```bash
python test_client.py
```

---

## 🧪 Comprehensive Test Suite

Run the full automated pytest suite (92 tests covering hardware isolation, image ops, agents, QA critic, REST API, and MCP tools):
```bash
pytest -v tests/
```

---

## 📡 REST API Reference

- `GET /health` — Health status, hardware profile, and dGPU isolation check.
- `GET /api/system` — CPU model, logical threads, PyTorch threads, memory, AVX-512 flags.
- `GET /api/presets` — Style aesthetics, filter presets, and aspect ratios.
- `POST /api/optimize` — AI Prompt Engineer enhancement.
- `POST /api/generate` — Text-to-Image generation with QA report.
- `POST /api/edit` — Image editing (AI img2img or instant CV filters).
- `POST /api/qa` — Image quality analysis (sharpness, contrast, clipping).
- `GET /api/history` — List recently generated/edited images.
- `GET /api/image/{filename}` — Download/view image output.

---

## 🛠️ MCP Tools Exposed

- `generate_image(prompt, style, negative_prompt, aspect_ratio, steps, guidance_scale, seed, auto_optimize)`
- `edit_image(image_path, prompt, filter_preset, brightness, contrast, saturation, sharpness, strength)`
- `optimize_prompt(prompt, style)`
- `analyze_image_quality(image_path)`
- `get_hardware_status()`

---

## 🔧 Backends

The `image_gen` service supports three operational backend modes:

### 1. Diffusers Backend (Default Real Mode: `diffusers:stabilityai/sd-turbo`)
- High-performance, low-latency diffusion inference using Hugging Face `diffusers` (`AutoPipelineForText2Image` and `AutoPipelineForImage2Image`).
- Model: `stabilityai/sd-turbo` (single-step to 4-step adversarial diffusion distillation).
- Hardware: GPU (CUDA fp16) accelerated when NVIDIA GPU is available (yielding < 1.0s generation latency on NVIDIA GeForce RTX 4070 Laptop GPU), with graceful fallback to multi-threaded CPU fp32 execution.
- Weights are shared across text-to-image and image-to-image pipelines to eliminate redundant VRAM/RAM allocation.
- Configuration variables:
  - `IMAGE_BACKEND`: `auto` (default) or `diffusers`.
  - `IMAGE_MODEL_ID`: Model repository identifier (defaults to `stabilityai/sd-turbo`).
- Output metadata reports `"backend": "diffusers:<model_id>"` (e.g. `diffusers:stabilityai/sd-turbo`).

### 2. Fast Test Mode (`FAST_TEST_MODE=1`)
- Generates deterministic, labelled placeholder images (`FAST TEST PLACEHOLDER`) with a vertical color gradient derived from the prompt hash.
- Requires no external backend, GPU hardware, or model weights.
- All pipeline stages (prompt optimization, quality assurance scoring, disk caching, metadata tagging) run authentically.
- Returns `"backend": "fast_test_placeholder"` in generation output metadata and MCP tool responses.

### 3. Optional Headless ComfyUI Backend (`IMAGE_BACKEND=comfyui`)
- Executes full diffusion inference via a headless ComfyUI backend when `IMAGE_BACKEND=comfyui` or when `COMFY_DIR` points to an installed ComfyUI tree.
- Configuration variables:
  - `COMFY_DIR`: Path to a valid ComfyUI directory containing `main.py` (e.g. `export COMFY_DIR=/path/to/ComfyUI`).
  - `COMFY_PORT`: ComfyUI HTTP port (defaults to `10099`).
- Required model weights (configured in `app/config.py`):
  - **Text / Vision Encoder**: `qwen3vl_8b_bf16_heretic.safetensors` (in `ComfyUI/models/clip/`)
  - **DiT Backbone**: `qwen_image_2.1_nvfp4.safetensors` (in `ComfyUI/models/diffusion_models/`)
  - **VAE**: `qwen_image_2.1_vae_bf16.safetensors` (in `ComfyUI/models/vae/`)
