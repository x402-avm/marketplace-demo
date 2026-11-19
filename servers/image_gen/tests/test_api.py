import pytest
from fastapi.testclient import TestClient
from runtime_server import app
from app.utils.image_utils import image_to_base64
from PIL import Image

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["dgpu_isolated"] is True
    assert data["device"] == "cpu"

def test_system_endpoint():
    response = client.get("/api/system")
    assert response.status_code == 200
    data = response.json()
    assert "cpu_model" in data
    assert data["dgpu_isolated"] is True
    assert "torch_threads" in data

def test_presets_endpoint():
    response = client.get("/api/presets")
    assert response.status_code == 200
    data = response.json()
    assert "styles" in data
    assert "filters" in data
    assert "aspect_ratios" in data

def test_optimize_endpoint():
    response = client.post("/api/optimize", json={
        "prompt": "futuristic flying car",
        "style": "cinematic_8k"
    })
    assert response.status_code == 200
    data = response.json()
    assert "optimized_prompt" in data
    assert "negative_prompt" in data

def test_generate_endpoint():
    response = client.post("/api/generate", json={
        "prompt": "sunset over mountains",
        "style": "photorealistic",
        "aspect_ratio": "1:1",
        "steps": 10,
        "auto_optimize": True,
        "run_qa": True
    })
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "image_base64" in data
    assert "qa_report" in data

def test_edit_endpoint():
    # Make small dummy image
    img = Image.new("RGB", (64, 64), color=(30, 60, 90))
    b64 = image_to_base64(img)
    
    response = client.post("/api/edit", json={
        "image_source": b64,
        "filter_preset": "auto_enhance",
        "brightness": 1.2,
        "contrast": 1.1,
        "sharpness": 1.5,
        "run_qa": True
    })
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "qa_report" in data

def test_static_ui_serving():
    response = client.get("/")
    assert response.status_code == 200
    assert "Gemini Nano" in response.text
    assert "Banana" in response.text
