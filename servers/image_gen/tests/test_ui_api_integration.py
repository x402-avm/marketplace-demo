"""Integration Tests: FastAPI Backend API + Frontend Static Mount Integration.
Validates the full request/response contract consumed by the Gemini Nano UI.
"""

import io
import pytest
from PIL import Image
from fastapi.testclient import TestClient

from app.main import app
from app.utils.image_utils import image_to_base64

client = TestClient(app)

@pytest.fixture
def sample_image_base64():
    """Create a 128x128 solid test image in base64."""
    img = Image.new("RGB", (128, 128), color=(70, 130, 180))
    return image_to_base64(img)

def test_frontend_root_mount():
    """Verify that GET / returns the Gemini Nano index.html."""
    response = client.get("/")
    assert response.status_code == 200
    assert "Gemini Nano" in response.text
    assert "Banana Edition" in response.text
    assert "<canvas" in response.text

def test_static_css_and_js_mount():
    """Verify that static directories /css and /js are served correctly."""
    css_resp = client.get("/css/variables.css")
    assert css_resp.status_code == 200
    assert "--gemini-purple" in css_resp.text

    js_resp = client.get("/js/api.js")
    assert js_resp.status_code == 200
    assert "ApiClient" in js_resp.text

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "Gemini Nano Image Engine"
    assert data["device"] == "cpu"
    assert data["dgpu_isolated"] is True

def test_system_hardware_profile():
    response = client.get("/api/system")
    assert response.status_code == 200
    hw = response.json()
    assert "cpu_model" in hw
    assert "torch_threads" in hw
    assert hw["device"] == "cpu"
    assert hw["dgpu_isolated"] is True
    assert "AMD" in hw["igpu_description"]

def test_presets_contract():
    response = client.get("/api/presets")
    assert response.status_code == 200
    data = response.json()
    assert "photorealistic" in data["styles"]
    assert "cyberpunk" in data["styles"]
    assert "cinematic" in data["filters"]
    assert "1:1" in data["aspect_ratios"]
    assert "16:9" in data["aspect_ratios"]

def test_prompt_optimization():
    response = client.post("/api/optimize", json={
        "prompt": "a sleek electric sports car",
        "style": "cyberpunk",
        "aspect_ratio": "16:9"
    })
    assert response.status_code == 200
    res = response.json()
    assert "optimized_prompt" in res
    assert "neon" in res["optimized_prompt"].lower() or "cyberpunk" in res["optimized_prompt"].lower()
    assert "negative_prompt" in res
    assert res["recommended_aspect_ratio"] == "16:9"

def test_generate_image_contract():
    response = client.post("/api/generate", json={
        "prompt": "serene mountain lake at sunrise",
        "style": "photorealistic",
        "aspect_ratio": "1:1",
        "steps": 10,
        "guidance_scale": 7.5,
        "seed": 42,
        "auto_optimize": True,
        "run_qa": True
    })
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "filename" in data
    assert "image_base64" in data
    assert data["image_base64"].startswith("data:image/png;base64,")
    assert "qa_report" in data
    assert "quality_score" in data["qa_report"]
    assert data["qa_report"]["passed_qa"] is True
    assert data["hardware"]["device"] == "cpu"
    assert data["hardware"]["dgpu_isolated"] is True

def test_edit_image_filters(sample_image_base64):
    response = client.post("/api/edit", json={
        "image_source": sample_image_base64,
        "edit_mode": "transform",
        "filter_preset": "noir",
        "brightness": 1.1,
        "contrast": 1.2,
        "saturation": 0.0,
        "sharpness": 1.3,
        "blur": 0.0,
        "vignette": 0.3,
        "run_qa": True
    })
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "filename" in data
    assert "image_base64" in data
    assert data["image_base64"].startswith("data:image/png;base64,")
    assert "qa_report" in data

def test_serve_index_html_direct():
    response = client.get("/index.html")
    assert response.status_code == 200
    assert "Gemini Nano" in response.text
    assert "Banana Edition" in response.text

def test_edit_image_with_mask(sample_image_base64):
    """Verify inpainting mask compositing."""
    # Create a 128x128 mask (white center box, black border)
    mask = Image.new("L", (128, 128), 0)
    # Paste 255 in center 64x64
    for y in range(32, 96):
        for x in range(32, 96):
            mask.putpixel((x, y), 255)
    mask_b64 = image_to_base64(mask)

    response = client.post("/api/edit", json={
        "image_source": sample_image_base64,
        "mask_source": mask_b64,
        "edit_mode": "transform",
        "filter_preset": "noir",
        "run_qa": False
    })
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "filename" in data
    assert "image_base64" in data
    # Verify inpainting compositor ran in audit log
    composited_actions = [log for log in data.get("audit_log", []) if "InpaintingCompositor" in log.get("agent", "")]
    assert len(composited_actions) > 0, "Expected inpainting compositor action in audit log"

def test_qa_audit_endpoint(sample_image_base64):
    response = client.post("/api/qa", json={
        "image_source": sample_image_base64
    })
    assert response.status_code == 200
    data = response.json()
    assert "quality_score" in data
    assert "grade" in data
    assert "metrics" in data
    assert "sharpness" in data["metrics"]
    assert "contrast" in data["metrics"]
    assert "exposure" in data["metrics"]
    assert "suggestions" in data

def test_history_and_image_retrieval(sample_image_base64):
    # Fetch history
    hist_resp = client.get("/api/history")
    assert hist_resp.status_code == 200
    history_data = hist_resp.json()
    assert "images" in history_data
    assert isinstance(history_data["images"], list)
    
    if len(history_data["images"]) > 0:
        first_img = history_data["images"][0]["filename"]
        img_resp = client.get(f"/api/image/{first_img}")
        assert img_resp.status_code == 200
        assert img_resp.headers["content-type"] == "image/png"
