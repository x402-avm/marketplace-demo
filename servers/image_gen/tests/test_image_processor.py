import pytest
import numpy as np
from PIL import Image
from app.image_ops.processor import ImageProcessor

@pytest.fixture
def test_sample_image():
    """Create a 128x128 synthetic test RGB image."""
    arr = np.zeros((128, 128, 3), dtype=np.uint8)
    # Red quadrant
    arr[0:64, 0:64] = [200, 50, 50]
    # Green quadrant
    arr[0:64, 64:128] = [50, 200, 50]
    # Blue quadrant
    arr[64:128, 0:64] = [50, 50, 200]
    # Yellow quadrant
    arr[64:128, 64:128] = [200, 200, 50]
    return Image.fromarray(arr, mode="RGB")

def test_brightness_adjustment(test_sample_image):
    original_mean = np.mean(np.array(test_sample_image))
    brightened = ImageProcessor.adjust_image(test_sample_image, brightness=1.5)
    darkened = ImageProcessor.adjust_image(test_sample_image, brightness=0.5)
    
    assert np.mean(np.array(brightened)) > original_mean
    assert np.mean(np.array(darkened)) < original_mean
    assert brightened.size == test_sample_image.size

def test_contrast_adjustment(test_sample_image):
    high_contrast = ImageProcessor.adjust_image(test_sample_image, contrast=1.5)
    low_contrast = ImageProcessor.adjust_image(test_sample_image, contrast=0.5)
    
    std_orig = np.std(np.array(test_sample_image))
    std_high = np.std(np.array(high_contrast))
    std_low = np.std(np.array(low_contrast))
    
    assert std_high > std_orig
    assert std_low < std_orig

def test_vignette_effect(test_sample_image):
    vignetted = ImageProcessor.apply_vignette(test_sample_image, intensity=0.8)
    arr_orig = np.array(test_sample_image)
    arr_vig = np.array(vignetted)
    
    # Corner pixels should be darker than center pixels
    center_y, center_x = 64, 64
    center_brightness = np.mean(arr_vig[center_y, center_x])
    corner_brightness = np.mean(arr_vig[0, 0])
    
    assert corner_brightness < center_brightness
    assert vignetted.size == test_sample_image.size

def test_all_preset_filters(test_sample_image):
    presets = [
        "cinematic", "hdr", "noir", "portrait_bokeh",
        "warm_golden", "cool_neon", "vintage", "pencil_sketch",
        "edge_detect", "auto_enhance"
    ]
    for preset in presets:
        result = ImageProcessor.apply_preset(test_sample_image, preset)
        assert isinstance(result, Image.Image)
        assert result.size == test_sample_image.size
        assert result.mode == "RGB"

def test_noir_preset_is_monochrome(test_sample_image):
    noir = ImageProcessor.apply_preset(test_sample_image, "noir")
    arr = np.array(noir)
    # In monochrome, R, G, B channels are approximately identical
    diff_rg = np.max(np.abs(arr[:, :, 0].astype(int) - arr[:, :, 1].astype(int)))
    diff_gb = np.max(np.abs(arr[:, :, 1].astype(int) - arr[:, :, 2].astype(int)))
    assert diff_rg == 0
    assert diff_gb == 0

def test_resize_image(test_sample_image):
    resized = ImageProcessor.resize_image(test_sample_image, 256, 128)
    assert resized.size == (256, 128)
    
    # Invalid size handling
    with pytest.raises(ValueError):
        ImageProcessor.resize_image(test_sample_image, 0, 100)

def test_crop_image(test_sample_image):
    cropped = ImageProcessor.crop_image(test_sample_image, 10, 10, 50, 60)
    assert cropped.size == (40, 50)

def test_rotate_and_flip(test_sample_image):
    rotated = ImageProcessor.rotate_image(test_sample_image, 90, expand=True)
    assert rotated.size == (128, 128)
    
    flipped_h = ImageProcessor.flip_image(test_sample_image, horizontal=True)
    flipped_v = ImageProcessor.flip_image(test_sample_image, horizontal=False)
    assert flipped_h.size == test_sample_image.size
    assert flipped_v.size == test_sample_image.size
