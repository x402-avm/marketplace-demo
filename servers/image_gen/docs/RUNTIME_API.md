# Runtime Server API Specification

Host: `http://127.0.0.1:10000`

### Endpoints

#### 1. System Health & Hardware
- `GET /health`
  Returns health status, active CPU model, and dGPU isolation state.
- `GET /api/system`
  Full hardware profile with CPU architecture, thread counts, AVX-512 flags, memory.

#### 2. AI Prompt Engineering
- `POST /api/optimize`
  Body: `{"prompt": "string", "style": "photorealistic", "aspect_ratio": "16:9"}`
  Returns optimized prompt, negative prompt, recommended steps, guidance scale.

#### 3. Image Generation
- `POST /api/generate`
  Body:
  ```json
  {
    "prompt": "sunset over futuristic city",
    "style": "cyberpunk",
    "aspect_ratio": "16:9",
    "steps": 15,
    "guidance_scale": 7.5,
    "seed": 42,
    "auto_optimize": true,
    "run_qa": true
  }
  ```
  Returns file path, base64 data URL, QA audit report, latency, hardware telemetry.

#### 4. Image Editing
- `POST /api/edit`
  Body:
  ```json
  {
    "image_source": "/path/to/image.png or data:image/png;base64,...",
    "filter_preset": "cinematic",
    "brightness": 1.1,
    "contrast": 1.2,
    "sharpness": 1.5,
    "blur": 0.0,
    "vignette": 0.3,
    "strength": 0.65,
    "run_qa": true
  }
  ```

#### 5. Quality Assurance Audit
- `POST /api/qa`
  Body: `{"image_source": "/path/to/image.png"}`
  Returns: Laplacian sharpness variance, RMS contrast, clipping percentages, 0-100 score, suggestions.

#### 6. History & Asset Retrieval
- `GET /api/history`
- `GET /api/image/{filename}`
