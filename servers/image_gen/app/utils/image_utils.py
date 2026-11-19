import io
import base64
from pathlib import Path
from PIL import Image

def image_to_base64(image: Image.Image, format: str = "PNG") -> str:
    """Encode PIL image to base64 data URL string."""
    buf = io.BytesIO()
    image.save(buf, format=format)
    buf.seek(0)
    encoded = base64.b64encode(buf.read()).decode("utf-8")
    mime = "image/png" if format.upper() == "PNG" else "image/jpeg"
    return f"data:{mime};base64,{encoded}"

def base64_to_image(b64_string: str) -> Image.Image:
    """Decode base64 data URL string or raw base64 to PIL Image."""
    if "," in b64_string:
        b64_string = b64_string.split(",", 1)[1]
    data = base64.b64decode(b64_string)
    buf = io.BytesIO(data)
    img = Image.open(buf)
    img.load()
    return img.convert("RGB")

from app.config import OUTPUTS_DIR
import re

def load_image_from_path_or_b64(source: str) -> Image.Image:
    """Load image from either a file path, filename in outputs, API URL, or a base64 string."""
    if not source or not isinstance(source, str):
        raise ValueError("Invalid image source: input cannot be empty.")
        
    source = source.strip()
    
    # 1. Base64 data URL
    if source.startswith("data:image/"):
        return base64_to_image(source)
        
    # 2. Check if direct file on disk exists (handles long paths safely)
    try:
        direct_path = Path(source)
        if direct_path.is_file():
            img = Image.open(direct_path)
            img.load()
            return img.convert("RGB")
    except Exception:
        pass
        
    # 3. Check /api/image/{filename} URL format
    if source.startswith("/api/image/"):
        filename = source.split("/api/image/", 1)[1].split("?")[0]
        candidate = OUTPUTS_DIR / filename
        if candidate.is_file():
            img = Image.open(candidate)
            img.load()
            return img.convert("RGB")
            
    # 4. Check filename in OUTPUTS_DIR
    try:
        filename_only = Path(source).name
        candidate = OUTPUTS_DIR / filename_only
        if candidate.is_file():
            img = Image.open(candidate)
            img.load()
            return img.convert("RGB")
    except Exception:
        pass
        
    # 5. Try raw base64 string if it matches base64 pattern
    clean_b64 = source.split(",", 1)[1] if "," in source else source
    # Must have reasonable length and valid base64 charset
    if len(clean_b64) >= 32 and re.match(r'^[A-Za-z0-9+/=\s]+$', clean_b64):
        try:
            return base64_to_image(source)
        except Exception:
            pass
            
    raise FileNotFoundError(f"Image not found at path or invalid base64: {source[:80]}")

def save_image_to_disk(image: Image.Image, directory: Path, filename: str) -> Path:
    """Save PIL image to disk and return path."""
    directory.mkdir(parents=True, exist_ok=True)
    out_path = directory / filename
    image.save(out_path, format="PNG")
    return out_path
