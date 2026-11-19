import math
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

class ImageProcessor:
    """High-performance CPU image processing and styling engine."""

    @staticmethod
    def adjust_image(
        image: Image.Image,
        brightness: float = 1.0,
        contrast: float = 1.0,
        saturation: float = 1.0,
        sharpness: float = 1.0,
        blur: float = 0.0,
        vignette: float = 0.0,
        gamma: float = 1.0
    ) -> Image.Image:
        """Apply parameterized adjustments to image."""
        img = image.convert("RGB")
        
        # Brightness
        if brightness != 1.0:
            enhancer = ImageEnhance.Brightness(img)
            img = enhancer.enhance(max(0.05, min(3.0, brightness)))
            
        # Contrast
        if contrast != 1.0:
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(max(0.1, min(3.0, contrast)))
            
        # Saturation (Color)
        if saturation != 1.0:
            enhancer = ImageEnhance.Color(img)
            img = enhancer.enhance(max(0.0, min(3.0, saturation)))
            
        # Sharpness
        if sharpness != 1.0:
            enhancer = ImageEnhance.Sharpness(img)
            img = enhancer.enhance(max(0.0, min(4.0, sharpness)))
            
        # Blur
        if blur > 0.0:
            radius = max(0.1, min(25.0, blur))
            img = img.filter(ImageFilter.GaussianBlur(radius=radius))
            
        # Gamma
        if gamma != 1.0:
            gamma = max(0.2, min(3.0, gamma))
            inv_gamma = 1.0 / gamma
            lut = [int(((i / 255.0) ** inv_gamma) * 255.0) for i in range(256)]
            img = img.point(lut * 3)
            
        # Vignette
        if vignette > 0.0:
            img = ImageProcessor.apply_vignette(img, intensity=vignette)
            
        return img

    @staticmethod
    def apply_vignette(image: Image.Image, intensity: float = 0.5) -> Image.Image:
        """Apply radial vignette shadow effect."""
        w, h = image.size
        intensity = max(0.0, min(1.0, intensity))
        
        # Create coordinate grid
        x = np.linspace(-1, 1, w)
        y = np.linspace(-1, 1, h)
        xx, yy = np.meshgrid(x, y)
        radius = np.sqrt(xx ** 2 + yy ** 2)
        
        # Radial mask
        max_r = np.sqrt(2)
        mask = 1.0 - (radius / max_r) * intensity
        mask = np.clip(mask, 0.0, 1.0)
        
        arr = np.array(image, dtype=np.float32)
        arr = arr * mask[:, :, np.newaxis]
        arr = np.clip(arr, 0, 255).astype(np.uint8)
        return Image.fromarray(arr)

    @staticmethod
    def apply_preset(image: Image.Image, preset_name: str) -> Image.Image:
        """Apply stylized aesthetic preset filters."""
        img = image.convert("RGB")
        name = preset_name.lower().strip()
        
        if name in ("cinematic", "film"):
            # Teal and orange color grade with rich contrast
            arr = np.array(img, dtype=np.float32)
            # Boost red/yellow highlights, boost cyan/blue shadows
            arr[:, :, 0] = np.clip(arr[:, :, 0] * 1.15, 0, 255)  # R
            arr[:, :, 2] = np.clip(arr[:, :, 2] * 1.10 + 10, 0, 255)  # B
            img = Image.fromarray(arr.astype(np.uint8))
            img = ImageEnhance.Contrast(img).enhance(1.25)
            img = ImageEnhance.Color(img).enhance(1.15)
            return ImageProcessor.apply_vignette(img, intensity=0.35)
            
        elif name in ("hdr", "vivid"):
            enh_c = ImageEnhance.Contrast(img).enhance(1.35)
            enh_s = ImageEnhance.Sharpness(enh_c).enhance(1.8)
            return ImageEnhance.Color(enh_s).enhance(1.4)
            
        elif name in ("noir", "monochrome", "bw"):
            gray = ImageOps.grayscale(img)
            contrast = ImageEnhance.Contrast(gray).enhance(1.45)
            sharp = ImageEnhance.Sharpness(contrast).enhance(1.3)
            rgb = sharp.convert("RGB")
            return ImageProcessor.apply_vignette(rgb, intensity=0.5)
            
        elif name in ("portrait_bokeh", "bokeh"):
            # Radial selective blur keeping center sharp
            w, h = img.size
            blurred = img.filter(ImageFilter.GaussianBlur(radius=8.0))
            
            # Gradient mask for center focus
            x = np.linspace(-1, 1, w)
            y = np.linspace(-1, 1, h)
            xx, yy = np.meshgrid(x, y)
            dist = np.sqrt(xx ** 2 + yy ** 2)
            mask_arr = np.clip((dist - 0.35) / 0.5, 0.0, 1.0)
            mask = Image.fromarray((mask_arr * 255).astype(np.uint8), mode="L")
            
            sharp_subject = ImageEnhance.Sharpness(img).enhance(1.2)
            composite = Image.composite(blurred, sharp_subject, mask)
            return composite
            
        elif name in ("warm_golden", "golden_hour"):
            arr = np.array(img, dtype=np.float32)
            arr[:, :, 0] = np.clip(arr[:, :, 0] * 1.20 + 15, 0, 255) # Red boost
            arr[:, :, 1] = np.clip(arr[:, :, 1] * 1.08 + 5, 0, 255)  # Green slight boost
            arr[:, :, 2] = np.clip(arr[:, :, 2] * 0.90, 0, 255)      # Blue reduce
            res = Image.fromarray(arr.astype(np.uint8))
            return ImageEnhance.Contrast(res).enhance(1.1)
            
        elif name in ("cool_neon", "cyberpunk"):
            arr = np.array(img, dtype=np.float32)
            arr[:, :, 0] = np.clip(arr[:, :, 0] * 1.25, 0, 255)  # Magenta/pink
            arr[:, :, 2] = np.clip(arr[:, :, 2] * 1.35 + 20, 0, 255) # Cyan/blue
            res = Image.fromarray(arr.astype(np.uint8))
            res = ImageEnhance.Contrast(res).enhance(1.3)
            return ImageEnhance.Color(res).enhance(1.4)
            
        elif name in ("vintage", "retro"):
            arr = np.array(img, dtype=np.float32)
            arr[:, :, 0] = np.clip(arr[:, :, 0] * 1.05 + 20, 0, 255)
            arr[:, :, 1] = np.clip(arr[:, :, 1] * 0.95 + 10, 0, 255)
            arr[:, :, 2] = np.clip(arr[:, :, 2] * 0.85, 0, 255)
            res = Image.fromarray(arr.astype(np.uint8))
            res = ImageEnhance.Contrast(res).enhance(0.9)
            res = ImageEnhance.Color(res).enhance(0.85)
            return ImageProcessor.apply_vignette(res, intensity=0.4)
            
        elif name in ("pencil_sketch", "sketch"):
            gray = ImageOps.grayscale(img)
            inv = ImageOps.invert(gray)
            blurred = inv.filter(ImageFilter.GaussianBlur(radius=15.0))
            
            g_arr = np.array(gray, dtype=np.float32)
            b_arr = np.array(blurred, dtype=np.float32)
            
            # Color dodge blend
            denom = 255.0 - b_arr
            denom[denom == 0] = 1.0
            sketch = (g_arr * 255.0) / denom
            sketch = np.clip(sketch, 0, 255).astype(np.uint8)
            return Image.fromarray(sketch).convert("RGB")
            
        elif name in ("edge_detect", "edges"):
            gray = ImageOps.grayscale(img)
            edges = gray.filter(ImageFilter.FIND_EDGES)
            return ImageEnhance.Contrast(edges).enhance(2.0).convert("RGB")
            
        elif name in ("auto_enhance", "crisp"):
            # Balanced auto-tone & crisp sharpen
            autocontrast = ImageOps.autocontrast(img, cutoff=1)
            sharp = ImageEnhance.Sharpness(autocontrast).enhance(1.4)
            return ImageEnhance.Color(sharp).enhance(1.1)
            
        return img

    @staticmethod
    def resize_image(image: Image.Image, width: int, height: int, keep_aspect_ratio: bool = False) -> Image.Image:
        """Resize image with high-quality Lanczos resampling."""
        if width <= 0 or height <= 0:
            raise ValueError(f"Invalid dimensions: {width}x{height}")
            
        if not keep_aspect_ratio:
            return image.resize((width, height), Image.Resampling.LANCZOS)
            
        # Fit inside bounding box
        img = image.copy()
        img.thumbnail((width, height), Image.Resampling.LANCZOS)
        
        # Letterbox onto black or transparent canvas
        canvas = Image.new("RGB", (width, height), (0, 0, 0))
        offset_x = (width - img.width) // 2
        offset_y = (height - img.height) // 2
        canvas.paste(img, (offset_x, offset_y))
        return canvas

    @staticmethod
    def crop_image(image: Image.Image, left: int, top: int, right: int, bottom: int) -> Image.Image:
        """Crop image with boundary clamping."""
        w, h = image.size
        clamped_left = max(0, min(w - 1, left))
        clamped_top = max(0, min(h - 1, top))
        clamped_right = max(clamped_left + 1, min(w, right))
        clamped_bottom = max(clamped_top + 1, min(h, bottom))
        return image.crop((clamped_left, clamped_top, clamped_right, clamped_bottom))

    @staticmethod
    def rotate_image(image: Image.Image, angle: float, expand: bool = True) -> Image.Image:
        """Rotate image by arbitrary angle."""
        return image.rotate(angle, resample=Image.Resampling.BICUBIC, expand=expand)

    @staticmethod
    def compose_multi_images(
        images: list,
        mode: str = "blend",
        target_size: tuple = (512, 512)
    ) -> Image.Image:
        """Compose or blend multiple input reference images into a unified conditioning canvas."""
        if not images:
            raise ValueError("No images provided for multi-image composition")
        if len(images) == 1:
            return ImageProcessor.resize_image(images[0], target_size[0], target_size[1])

        # Normalize all images to target size RGB
        norm_images = [ImageProcessor.resize_image(img.convert("RGB"), target_size[0], target_size[1]) for img in images]

        if mode == "blend":
            # Progressive alpha blend
            acc = norm_images[0]
            for i, next_img in enumerate(norm_images[1:], start=1):
                alpha = 1.0 / (i + 1)
                acc = Image.blend(acc, next_img, alpha=alpha)
            return acc

        elif mode in ("grid", "side_by_side"):
            n = len(norm_images)
            if n == 2 and mode == "side_by_side":
                w, h = target_size
                half_w = w // 2
                canvas = Image.new("RGB", (w, h), (0, 0, 0))
                im1 = ImageProcessor.resize_image(norm_images[0], half_w, h)
                im2 = ImageProcessor.resize_image(norm_images[1], w - half_w, h)
                canvas.paste(im1, (0, 0))
                canvas.paste(im2, (half_w, 0))
                return canvas
            else:
                # 2x2 or Nx1 arrangement
                cols = 2 if n >= 2 else 1
                rows = (n + cols - 1) // cols
                tile_w = target_size[0] // cols
                tile_h = target_size[1] // rows
                canvas = Image.new("RGB", target_size, (0, 0, 0))
                for idx, im in enumerate(norm_images[:4]):
                    r = idx // cols
                    c = idx % cols
                    tile = ImageProcessor.resize_image(im, tile_w, tile_h)
                    canvas.paste(tile, (c * tile_w, r * tile_h))
                return canvas

        elif mode == "overlay":
            # Primary base image with smaller reference thumbnails overlaid
            base = norm_images[0].copy()
            thumb_size = (target_size[0] // 3, target_size[1] // 3)
            for idx, im in enumerate(norm_images[1:4]):
                thumb = ImageProcessor.resize_image(im, thumb_size[0], thumb_size[1])
                pos = (target_size[0] - thumb_size[0] - 10, 10 + idx * (thumb_size[1] + 10))
                base.paste(thumb, pos)
            return base

        return norm_images[0]

    @staticmethod
    def flip_image(image: Image.Image, horizontal: bool = True) -> Image.Image:
        """Flip image horizontally or vertically."""
        if horizontal:
            return image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        return image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
