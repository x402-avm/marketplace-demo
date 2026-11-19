/**
 * Gemini Nano & Banana - Side-by-Side & Split-Screen Comparison
 * Provides interactive draggable divider and side-by-side dual column modes
 */

class ImageComparison {
  constructor(options = {}) {
    const getEl = (id) => (typeof document !== 'undefined' && id ? document.getElementById(id) : null);
    this.container = getEl(options.containerId || "comparisonContainer");
    this.beforeWrapper = getEl(options.beforeWrapperId || "comparisonBeforeWrapper");
    this.beforeImg = getEl(options.beforeImgId || "comparisonImgBefore");
    this.afterImg = getEl(options.afterImgId || "comparisonImgAfter");
    this.handle = getEl(options.handleId || "comparisonHandle");
    this.dualColumnView = getEl(options.dualColumnId || "dualColumnView");
    this.dualBeforeImg = getEl(options.dualBeforeImgId || "dualBeforeImg");
    this.dualAfterImg = getEl(options.dualAfterImgId || "dualAfterImg");

    this.isDragging = false;
    this.currentPositionPercent = 50; // 0 to 100
    this.mode = 'slider'; // 'slider' or 'dual'

    if (this.container && this.handle) {
      this.initEvents();
    }
  }

  setImages(beforeSrc, afterSrc) {
    if (this.beforeImg) this.beforeImg.src = beforeSrc;
    if (this.afterImg) this.afterImg.src = afterSrc;
    if (this.dualBeforeImg) this.dualBeforeImg.src = beforeSrc;
    if (this.dualAfterImg) this.dualAfterImg.src = afterSrc;
    this.setPosition(50);
  }

  initEvents() {
    // Mouse events on handle / container
    this.handle.addEventListener("mousedown", (e) => {
      this.isDragging = true;
      e.preventDefault();
    });

    this.container.addEventListener("mousedown", (e) => {
      if (e.target !== this.handle) {
        this.isDragging = true;
        this.updateFromClientX(e.clientX);
      }
    });

    window.addEventListener("mousemove", (e) => {
      if (!this.isDragging) return;
      this.updateFromClientX(e.clientX);
    });

    window.addEventListener("mouseup", () => {
      this.isDragging = false;
    });

    // Touch events
    this.handle.addEventListener("touchstart", (e) => {
      this.isDragging = true;
      e.preventDefault();
    }, { passive: false });

    this.container.addEventListener("touchstart", (e) => {
      if (e.touches.length === 1) {
        this.isDragging = true;
        this.updateFromClientX(e.touches[0].clientX);
      }
    }, { passive: false });

    window.addEventListener("touchmove", (e) => {
      if (!this.isDragging || e.touches.length !== 1) return;
      if (e.cancelable) e.preventDefault();
      this.updateFromClientX(e.touches[0].clientX);
    }, { passive: false });

    window.addEventListener("touchend", () => {
      this.isDragging = false;
    });

    // Window resize to align width of before image with container
    window.addEventListener("resize", () => {
      this.syncDimensions();
    });

    if (typeof ResizeObserver !== "undefined" && this.container) {
      try {
        this.resizeObserver = new ResizeObserver(() => this.syncDimensions());
        this.resizeObserver.observe(this.container);
      } catch (_) {}
    }
  }

  updateFromClientX(clientX) {
    if (!this.container) return;
    const rect = this.container.getBoundingClientRect();
    const x = clientX - rect.left;
    const percent = Math.max(0, Math.min(100, (x / rect.width) * 100));
    this.setPosition(percent);
  }

  setPosition(percent) {
    this.currentPositionPercent = percent;
    if (this.beforeWrapper) {
      this.beforeWrapper.style.width = `${percent}%`;
    }
    if (this.handle) {
      this.handle.style.left = `${percent}%`;
    }
    this.syncDimensions();
  }

  syncDimensions() {
    if (!this.container || !this.beforeImg) return;
    const width = this.container.clientWidth;
    if (width > 0) {
      this.beforeImg.style.width = `${width}px`;
    }
  }

  setMode(mode) {
    this.mode = mode;
    if (mode === 'dual') {
      if (this.container) this.container.style.display = 'none';
      if (this.dualColumnView) this.dualColumnView.style.display = 'grid';
    } else {
      if (this.container) this.container.style.display = 'block';
      if (this.dualColumnView) this.dualColumnView.style.display = 'none';
      this.syncDimensions();
    }
  }
}

// Export for tests & module loaders
if (typeof module !== "undefined" && module.exports) {
  module.exports = { ImageComparison };
}
