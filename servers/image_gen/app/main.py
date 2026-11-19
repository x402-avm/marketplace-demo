"""Main entrypoint for Gemini Nano Image Generation & Editing Engine.
Runs on Port 10000 strictly conforming to the 10000-10100 port range.
Serves API routes and mounts the Gemini Nano frontend interface.
"""

import os
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import SERVER_HOST, SERVER_PORT, BASE_DIR, STATIC_DIR
from app.api.routes import router
from app.utils.hardware import get_system_hardware_profile
from app.utils.oom_guard import oom_guard

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start OOM Protection Watchdog
    oom_guard.start_watchdog()
    profile = get_system_hardware_profile()
    print("=" * 65)
    print("🚀 GEMINI NANO BANANA RUNTIME SERVER INITIALIZED")
    print(f" • CPU Architecture: {profile['cpu_model']}")
    print(f" • Zen 5 Logical Threads: {profile['cpu_cores_logical']}")
    print(f" • PyTorch Active Threads: {profile['torch_threads']}")
    print(f" • AVX-512 Support: {profile['avx512_supported']}")
    print(f" • Discrete GPU Isolation: {'STRICTLY ENFORCED' if profile['dgpu_isolated'] else 'FAILED'}")
    print(f" • OOM Fail-Safe Watchdog: ACTIVE (Emergency shutdown at {oom_guard.max_ram_percent}%, Pre-flight limit {oom_guard.preflight_limit_percent}%)")
    print(f" • Bound Address: http://{SERVER_HOST}:{SERVER_PORT}")
    print("=" * 65)
    try:
        yield
    finally:
        oom_guard.stop_watchdog()

app = FastAPI(
    title="Gemini Nano Image Engine",
    description="High-performance CPU image generation and editing for AMD Ryzen AI 9 HX 370 with complete dGPU isolation.",
    version="2.0.0",
    lifespan=lifespan
)

# Enable CORS for cross-origin access across ports 10000-10100
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router)

# Mount frontend static directory
FRONTEND_DIR = BASE_DIR / "frontend"
if FRONTEND_DIR.is_dir():
    # Mount css, js, assets
    for sub in ["css", "js", "assets"]:
        subdir = FRONTEND_DIR / sub
        if subdir.is_dir():
            app.mount(f"/{sub}", StaticFiles(directory=subdir), name=sub)

# Mount /static for static directory backward compatibility
if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/")
@app.head("/")
@app.get("/index.html")
@app.head("/index.html")
def serve_ui():
    """Serve Gemini Nano & Banana Web Interface."""
    index_file = FRONTEND_DIR / "index.html"
    if index_file.is_file():
        return FileResponse(index_file)
    static_index = STATIC_DIR / "index.html"
    if static_index.is_file():
        return FileResponse(static_index)
    return {"status": "ok", "message": "Gemini Nano Engine online"}

if __name__ == "__main__":
    import uvicorn
    print(f"Starting Gemini Nano Engine on {SERVER_HOST}:{SERVER_PORT}...")
    uvicorn.run("app.main:app", host=SERVER_HOST, port=SERVER_PORT, reload=False)
