import pytest
import numpy as np
from PIL import Image
from app.agents.qa_critic import QualityAssuranceAgent

@pytest.fixture
def qa_agent():
    return QualityAssuranceAgent()

def test_qa_balanced_image(qa_agent):
    # Create natural gradient with edges
    arr = np.zeros((200, 200, 3), dtype=np.uint8)
    for i in range(200):
        for j in range(200):
            arr[i, j] = [(i * 20) % 255, (j * 15) % 255, ((i + j) * 10) % 255]
    img = Image.fromarray(arr)
    
    report = qa_agent.analyze_image(img)
    assert "quality_score" in report
    assert 0.0 <= report["quality_score"] <= 100.0
    assert "grade" in report
    assert "metrics" in report
    assert report["passed_qa"] is True

def test_qa_all_black_image(qa_agent):
    # Completely black image should detect massive shadow clipping
    arr = np.zeros((100, 100, 3), dtype=np.uint8)
    img = Image.fromarray(arr)
    
    report = qa_agent.analyze_image(img)
    assert report["metrics"]["shadow_clipping_percent"] == 100.0
    assert report["quality_score"] < 50.0

def test_qa_all_white_image(qa_agent):
    # Completely white image should detect massive highlight clipping
    arr = np.full((100, 100, 3), 255, dtype=np.uint8)
    img = Image.fromarray(arr)
    
    report = qa_agent.analyze_image(img)
    assert report["metrics"]["highlight_clipping_percent"] == 100.0
    assert report["quality_score"] < 50.0

def test_qa_blurry_vs_sharp(qa_agent):
    from PIL import ImageFilter
    # Create high-contrast pattern
    arr = np.random.randint(0, 256, (120, 120, 3), dtype=np.uint8)
    sharp_img = Image.fromarray(arr)
    blurred_img = sharp_img.filter(ImageFilter.GaussianBlur(radius=6.0))
    
    sharp_rep = qa_agent.analyze_image(sharp_img)
    blur_rep = qa_agent.analyze_image(blurred_img)
    
    assert sharp_rep["metrics"]["sharpness"] > blur_rep["metrics"]["sharpness"]
