/**
 * Gemini Nano Image Studio - Interactive Canvas & Masking Engine
 * Supports High-DPI rendering, Zoom/Pan, Inpainting Mask Drawing, Eraser, and Live Filters
 */

class StudioCanvas {
  constructor(options = {}) {
    const getEl = (id) => (typeof document !== 'undefined' && id ? document.getElementById(id) : null);
    this.viewport = getEl(options.viewportId || "canvasViewport");
    this.panContainer = getEl(options.panContainerId || "panContainer");
    this.imgCanvas = getEl(options.imageCanvasId || "imageCanvas");
    this.maskCanvas = getEl(options.maskCanvasId || "maskCanvas");
    this.cursorIndicator = getEl("brushCursorIndicator");

    this.imgCtx = this.imgCanvas && typeof this.imgCanvas.getContext === 'function' ? this.imgCanvas.getContext("2d") : null;
    this.maskCtx = this.maskCanvas && typeof this.maskCanvas.getContext === 'function' ? this.maskCanvas.getContext("2d") : null;

    // State
    this.currentImage = null; // HTMLImageElement
    this.originalImageSrc = null;
    this.scale = 1.0;
    this.panX = 0;
    this.panY = 0;
    
    // Tools: 'brush', 'eraser', 'pan'
    this.activeTool = 'brush';
    this.brushSize = 30;
    this.brushColor = 'rgba(239, 68, 68, 0.7)'; // Translucent Red for mask
    this.isDrawing = false;
    this.isPanning = false;
    this.lastX = 0;
    this.lastY = 0;
    this.panStartX = 0;
    this.panStartY = 0;

    // Mask undo stack
    this.maskHistory = [];
    this.maxHistory = 15;

    // Adjustments for live preview
    this.adjustments = {
      brightness: 1.0,
      contrast: 1.0,
      saturation: 1.0,
      sharpness: 1.0,
      blur: 0,
      vignette: 0,
      gamma: 1.0
    };

    if (this.viewport && this.panContainer && this.maskCanvas) {
      this.initEventListeners();
    }
  }

  initEventListeners() {
    // Mouse events on mask canvas for drawing
    this.maskCanvas.addEventListener('mousedown', (e) => this.onMouseDown(e));
    window.addEventListener('mousemove', (e) => this.onMouseMove(e));
    window.addEventListener('mouseup', () => this.onMouseUp());

    // Spacebar panning support
    this.spacePressed = false;
    window.addEventListener('keydown', (e) => {
      if (e.code === 'Space' && !['INPUT', 'TEXTAREA'].includes(document.activeElement?.tagName)) {
        this.spacePressed = true;
        if (this.viewport && (this.viewport.matches?.(':hover') || this.viewport.contains(document.activeElement || null))) {
          e.preventDefault();
        }
        if (this.panContainer) this.panContainer.classList.add('panning');
      }
    });

    window.addEventListener('keyup', (e) => {
      if (e.code === 'Space') {
        this.spacePressed = false;
        if (this.activeTool !== 'pan' && this.panContainer) {
          this.panContainer.classList.remove('panning');
        }
      }
    });

    // Touch events for mobile/tablet drawing
    this.maskCanvas.addEventListener('touchstart', (e) => {
      if (e.touches.length === 1) {
        const touch = e.touches[0];
        const fakeMouse = {
          clientX: touch.clientX,
          clientY: touch.clientY,
          button: 0,
          preventDefault: () => e.preventDefault()
        };
        this.onMouseDown(fakeMouse);
      }
    }, { passive: false });

    window.addEventListener('touchmove', (e) => {
      if (this.isDrawing && e.touches.length === 1) {
        if (e.cancelable) e.preventDefault();
        const touch = e.touches[0];
        const fakeMouse = {
          clientX: touch.clientX,
          clientY: touch.clientY
        };
        this.onMouseMove(fakeMouse);
      }
    }, { passive: false });

    window.addEventListener('touchend', () => {
      if (this.isDrawing) this.onMouseUp();
    });

    // Zoom on wheel inside viewport
    this.viewport.addEventListener('wheel', (e) => {
      e.preventDefault();
      const zoomFactor = e.deltaY < 0 ? 1.1 : 0.9;
      this.zoom(zoomFactor, e.clientX, e.clientY);
    }, { passive: false });

    // Hover brush cursor
    this.viewport.addEventListener('mouseenter', () => {
      if (this.activeTool !== 'pan' && this.cursorIndicator) {
        this.cursorIndicator.style.display = 'block';
      }
    });

    this.viewport.addEventListener('mouseleave', () => {
      if (this.cursorIndicator) {
        this.cursorIndicator.style.display = 'none';
      }
    });
  }

  loadImage(src) {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.crossOrigin = "anonymous";
      img.onload = () => {
        const MAX_DIM = 1280;
        let w = img.naturalWidth || 512;
        let h = img.naturalHeight || 512;
        if (w > MAX_DIM || h > MAX_DIM) {
          if (w > h) {
            h = Math.round((h * MAX_DIM) / w);
            w = MAX_DIM;
          } else {
            w = Math.round((w * MAX_DIM) / h);
            h = MAX_DIM;
          }
        }
        this.currentImage = img;
        this.originalImageSrc = src;
        this.setupDimensions(w, h);
        this.drawImage();
        this.clearMask();
        this.resetTransform();
        resolve(img);
      };
      img.onerror = (err) => reject(err);
      img.src = src;
    });
  }

  setupDimensions(width, height) {
    this.imgCanvas.width = width;
    this.imgCanvas.height = height;
    this.maskCanvas.width = width;
    this.maskCanvas.height = height;

    this.panContainer.style.width = `${width}px`;
    this.panContainer.style.height = `${height}px`;

    // Reset mask history
    this.maskHistory = [];
  }

  drawImage() {
    if (!this.currentImage || !this.imgCtx) return;
    this.imgCtx.clearRect(0, 0, this.imgCanvas.width, this.imgCanvas.height);
    
    // Apply live CSS filter to image canvas for instantaneous visual response
    const fBrightness = this.adjustments.brightness;
    const fContrast = this.adjustments.contrast;
    const fSaturate = this.adjustments.saturation;
    const fBlur = this.adjustments.blur;
    
    this.imgCtx.filter = `brightness(${fBrightness}) contrast(${fContrast}) saturate(${fSaturate}) blur(${fBlur}px)`;
    this.imgCtx.drawImage(this.currentImage, 0, 0, this.imgCanvas.width, this.imgCanvas.height);
    this.imgCtx.filter = 'none';
  }

  updateAdjustments(newAdjustments) {
    this.adjustments = { ...this.adjustments, ...newAdjustments };
    this.drawImage();
  }

  resetAdjustments() {
    this.adjustments = {
      brightness: 1.0,
      contrast: 1.0,
      saturation: 1.0,
      sharpness: 1.0,
      blur: 0,
      vignette: 0,
      gamma: 1.0
    };
    this.drawImage();
  }

  setTool(tool) {
    this.activeTool = tool;
    if (tool === 'pan') {
      if (this.panContainer) this.panContainer.classList.add('panning');
      if (this.cursorIndicator) this.cursorIndicator.style.display = 'none';
    } else {
      if (this.panContainer) this.panContainer.classList.remove('panning');
      if (this.cursorIndicator) this.cursorIndicator.style.display = 'block';
    }
  }

  setBrushSize(size) {
    this.brushSize = Math.max(2, Math.min(200, size));
    this.updateCursorSize();
  }

  updateCursorSize() {
    if (!this.cursorIndicator) return;
    const displaySize = this.brushSize * this.scale;
    this.cursorIndicator.style.width = `${displaySize}px`;
    this.cursorIndicator.style.height = `${displaySize}px`;
  }

  getCanvasCoords(e) {
    const rect = this.maskCanvas.getBoundingClientRect();
    const x = (e.clientX - rect.left) * (this.maskCanvas.width / rect.width);
    const y = (e.clientY - rect.top) * (this.maskCanvas.height / rect.height);
    return { x, y };
  }

  saveMaskState() {
    if (!this.maskCtx) return;
    const imageData = this.maskCtx.getImageData(0, 0, this.maskCanvas.width, this.maskCanvas.height);
    this.maskHistory.push(imageData);
    if (this.maskHistory.length > this.maxHistory) {
      this.maskHistory.shift();
    }
  }

  undoMask() {
    if (!this.maskCtx || this.maskHistory.length === 0) return false;
    const prevState = this.maskHistory.pop();
    this.maskCtx.putImageData(prevState, 0, 0);
    return true;
  }

  clearMask() {
    if (!this.maskCtx) return;
    this.saveMaskState();
    this.maskCtx.clearRect(0, 0, this.maskCanvas.width, this.maskCanvas.height);
  }

  onMouseDown(e) {
    if (this.activeTool === 'pan' || e.button === 1 || this.spacePressed) {
      this.isPanning = true;
      this.panStartX = e.clientX - this.panX;
      this.panStartY = e.clientY - this.panY;
      return;
    }

    if (e.button === 0 && (this.activeTool === 'brush' || this.activeTool === 'eraser')) {
      this.saveMaskState();
      this.isDrawing = true;
      const { x, y } = this.getCanvasCoords(e);
      this.lastX = x;
      this.lastY = y;
      this.drawStroke(x, y, x, y);
    }
  }

  onMouseMove(e) {
    // Update cursor position and size
    if (this.cursorIndicator && this.activeTool !== 'pan') {
      this.cursorIndicator.style.left = `${e.clientX}px`;
      this.cursorIndicator.style.top = `${e.clientY}px`;
      this.updateCursorSize();
    }

    if (this.isPanning) {
      this.panX = e.clientX - this.panStartX;
      this.panY = e.clientY - this.panStartY;
      this.applyTransform();
      return;
    }

    if (this.isDrawing) {
      const { x, y } = this.getCanvasCoords(e);
      this.drawStroke(this.lastX, this.lastY, x, y);
      this.lastX = x;
      this.lastY = y;
    }
  }

  onMouseUp() {
    this.isDrawing = false;
    this.isPanning = false;
  }

  drawStroke(fromX, fromY, toX, toY) {
    if (!this.maskCtx) return;

    this.maskCtx.save();
    this.maskCtx.lineWidth = this.brushSize;
    this.maskCtx.lineCap = 'round';
    this.maskCtx.lineJoin = 'round';

    if (this.activeTool === 'eraser') {
      this.maskCtx.globalCompositeOperation = 'destination-out';
      this.maskCtx.strokeStyle = 'rgba(0,0,0,1)';
    } else {
      this.maskCtx.globalCompositeOperation = 'source-over';
      this.maskCtx.strokeStyle = this.brushColor;
    }

    this.maskCtx.beginPath();
    this.maskCtx.moveTo(fromX, fromY);
    this.maskCtx.lineTo(toX, toY);
    this.maskCtx.stroke();
    this.maskCtx.restore();
  }

  zoom(factor, clientX, clientY) {
    const prevScale = this.scale;
    const newScale = Math.min(5.0, Math.max(0.1, this.scale * factor));
    if (newScale === prevScale) return;

    // Zoom centered towards mouse or viewport center
    const vpRect = this.viewport.getBoundingClientRect();
    const centerX = clientX ? (clientX - vpRect.left) : (vpRect.width / 2);
    const centerY = clientY ? (clientY - vpRect.top) : (vpRect.height / 2);

    this.panX = centerX - (centerX - this.panX) * (newScale / prevScale);
    this.panY = centerY - (centerY - this.panY) * (newScale / prevScale);
    this.scale = newScale;

    this.applyTransform();
    this.updateCursorSize();
  }

  resetTransform() {
    if (!this.currentImage || !this.viewport) return;
    const vpRect = this.viewport.getBoundingClientRect();
    const imgW = this.currentImage.naturalWidth || 512;
    const imgH = this.currentImage.naturalHeight || 512;

    const scaleX = (vpRect.width - 48) / imgW;
    const scaleY = (vpRect.height - 48) / imgH;
    this.scale = Math.min(1.0, Math.min(scaleX, scaleY));

    this.panX = (vpRect.width - imgW * this.scale) / 2;
    this.panY = (vpRect.height - imgH * this.scale) / 2;

    this.applyTransform();
    this.updateCursorSize();
  }

  applyTransform() {
    if (!this.panContainer) return;
    this.panContainer.style.transform = `translate(${this.panX}px, ${this.panY}px) scale(${this.scale})`;
  }

  exportMaskBase64() {
    if (!this.maskCanvas) return null;
    // Export high-contrast binary mask (white = masked/inpainted, black = preserved)
    const exportCanvas = document.createElement("canvas");
    exportCanvas.width = this.maskCanvas.width;
    exportCanvas.height = this.maskCanvas.height;
    const ctx = exportCanvas.getContext("2d");

    // Fill background black
    ctx.fillStyle = "#000000";
    ctx.fillRect(0, 0, exportCanvas.width, exportCanvas.height);

    // Read mask alpha channel
    const maskData = this.maskCtx.getImageData(0, 0, this.maskCanvas.width, this.maskCanvas.height);
    const outputData = ctx.getImageData(0, 0, exportCanvas.width, exportCanvas.height);
    const data = maskData.data;
    const out = outputData.data;

    let hasMask = false;
    for (let i = 0; i < data.length; i += 4) {
      if (data[i + 3] > 20) { // Alpha threshold
        out[i] = 255;     // R
        out[i + 1] = 255; // G
        out[i + 2] = 255; // B
        out[i + 3] = 255; // A
        hasMask = true;
      }
    }

    if (!hasMask) return null;
    ctx.putImageData(outputData, 0, 0);
    return exportCanvas.toDataURL("image/png");
  }

  getImageBase64() {
    return this.imgCanvas ? this.imgCanvas.toDataURL("image/png") : null;
  }

  getEffectiveSourceImage() {
    // If original source is massive (>2MB data URL), return scaled canvas data URL to save bandwidth
    if (this.imgCanvas && this.originalImageSrc && this.originalImageSrc.length > 2000000) {
      return this.imgCanvas.toDataURL("image/png");
    }
    return this.originalImageSrc || this.getImageBase64();
  }
}

// Export for tests & module loaders
if (typeof module !== "undefined" && module.exports) {
  module.exports = { StudioCanvas };
}
