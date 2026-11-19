import pytest
import numpy as np
from PIL import Image
from app.image_ops.processor import ImageProcessor

@pytest.fixture
def sample_image():
    arr = np.zeros((100, 100, 3), dtype=np.uint8)
    arr[:, :50] = [200, 100, 50]
    arr[:, 50:] = [50, 150, 220]
    return Image.fromarray(arr)

def test_adjust_image_brightness(sample_image):
    brightened = ImageProcessor.adjust_image(sample_image, brightness=1.5)
    assert brightened.size == sample_image.size
    orig_mean = np.mean(np.array(sample_image))
    new_mean = np.mean(np.array(brightened))
    assert new_mean > orig_mean

def test_adjust_image_contrast(sample_image):
    high_contrast = ImageProcessor.adjust_image(sample_image, contrast=1.8)
    assert high_contrast.size == sample_image.size

def test_adjust_image_saturation(sample_image):
    desaturated = ImageProcessor.adjust_image(sample_image, saturation=0.0)
    arr = np.array(desaturated)
    # R, G, B should be virtually identical when grayscale/desaturated
    assert np.allclose(arr[:, :, 0], arr[:, :, 1], atol=2)

def test_adjust_image_blur_and_vignette(sample_image):
    blurred = ImageProcessor.adjust_image(sample_image, blur=2.0, vignette=0.5)
    assert blurred.size == sample_image.size

def test_apply_presets(sample_image):
    presets = [
        "cinematic", "hdr", "noir", "portrait_bokeh",
        "warm_golden", "cool_neon", "vintage", "pencil_sketch",
        "edge_detect", "auto_enhance"
    ]
    for p in presets:
        result = ImageProcessor.apply_preset(sample_image, p)
        assert result.size == sample_image.size
        assert result.mode == "RGB"

def test_resize_and_crop(sample_image):
    resized = ImageProcessor.resize_image(sample_image, 64, 48)
    assert resized.size == (64, 48)
    
    letterboxed = ImageProcessor.resize_image(sample_image, 120, 120, keep_aspect_ratio=True)
    assert letterboxed.size == (120, 120)
    
    cropped = ImageProcessor.crop_image(sample_image, 10, 10, 80, 80)
    assert cropped.size == (70, 70)

def test_rotate_and_flip(sample_image):
    rotated = ImageProcessor.rotate_image(sample_image, 90)
    assert rotated.size == (100, 100)
    
    flipped_h = ImageProcessor.flip_image(sample_image, horizontal=True)
    assert flipped_h.size == sample_image.size
    
    flipped_v = ImageProcessor.flip_image(sample_image, horizontal=False)
    assert flipped_v.size == sample_image.size
