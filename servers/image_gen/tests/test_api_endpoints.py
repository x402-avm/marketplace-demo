import pytest
from fastapi.testclient import TestClient
from runtime_server import app

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c

def test_health_endpoint(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["device"] == "cpu"
    assert data["dgpu_isolated"] is True

def test_system_hardware_endpoint(client):
    resp = client.get("/api/system")
    assert resp.status_code == 200
    data = resp.json()
    assert "cpu_model" in data
    assert data["dgpu_isolated"] is True
    assert data["device"] == "cpu"
    assert data["status"] == "production_ready_cpu_optimized"

def test_presets_endpoint(client):
    resp = client.get("/api/presets")
    assert resp.status_code == 200
    data = resp.json()
    assert "styles" in data
    assert "filters" in data
    assert "aspect_ratios" in data
    assert "photorealistic" in data["styles"]
    assert "cinematic" in data["filters"]
    assert "16:9" in data["aspect_ratios"]

def test_prompt_optimize_endpoint(client):
    resp = client.post(
        "/api/optimize",
        json={
            "prompt": "majestic eagle flying over mountain range",
            "style": "cinematic_8k"
        }
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "optimized_prompt" in data
    assert "Cinematic film still of" in data["optimized_prompt"]
    assert "negative_prompt" in data

def test_generate_image_endpoint(client):
    resp = client.post(
        "/api/generate",
        json={
            "prompt": "vibrant neon cyberpunk cityscape with rain reflections",
            "style": "cyberpunk",
            "aspect_ratio": "16:9",
            "steps": 5,
            "guidance_scale": 7.0,
            "seed": 42,
            "auto_optimize": True,
            "run_qa": True
        }
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "filename" in data
    assert "image_base64" in data
    assert data["image_base64"].startswith("data:image/png;base64,")
    assert "qa_report" in data
    assert data["qa_report"]["passed_qa"] is True
    assert data["hardware"]["device"] == "cpu"
    assert data["hardware"]["dgpu_isolated"] is True

def test_edit_image_endpoint(client):
    # First generate an image
    gen_resp = client.post(
        "/api/generate",
        json={"prompt": "tranquil forest lake", "style": "photorealistic", "steps": 5, "seed": 77}
    )
    assert gen_resp.status_code == 200
    gen_data = gen_resp.json()
    base64_src = gen_data["image_base64"]
    
    # Now edit the image using filters and parametric tuning
    edit_resp = client.post(
        "/api/edit",
        json={
            "image_source": base64_src,
            "edit_mode": "transform",
            "filter_preset": "hdr",
            "brightness": 1.15,
            "contrast": 1.2,
            "vignette": 0.3,
            "run_qa": True
        }
    )
    assert edit_resp.status_code == 200
    edit_data = edit_resp.json()
    assert edit_data["success"] is True
    assert "filename" in edit_data
    assert edit_data["image_base64"].startswith("data:image/png;base64,")
    assert "qa_report" in edit_data
    assert edit_data["qa_report"]["passed_qa"] is True

def test_qa_endpoint(client):
    gen_resp = client.post(
        "/api/generate",
        json={"prompt": "modern luxury architecture", "style": "photorealistic", "steps": 5, "seed": 12}
    )
    base64_src = gen_resp.json()["image_base64"]
    
    resp = client.post("/api/qa", json={"image_source": base64_src})
    assert resp.status_code == 200
    data = resp.json()
    assert "quality_score" in data
    assert "grade" in data
    assert "metrics" in data

def test_history_and_image_retrieval(client):
    hist_resp = client.get("/api/history")
    assert hist_resp.status_code == 200
    images = hist_resp.json()["images"]
    assert len(images) > 0
    
    target_img = images[0]["filename"]
    img_resp = client.get(f"/api/image/{target_img}")
    assert img_resp.status_code == 200
    assert img_resp.headers["content-type"] == "image/png"
    assert len(img_resp.content) > 100

def test_serve_ui_root(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "Gemini Nano" in resp.text
    assert "Banana" in resp.text
