/**
 * Gemini Nano & Banana Image Engine - API Client
 * Supports seamless communication with Backend Server on Port 10000
 */

class ApiClient {
  constructor() {
    this.storageKey = "gemini_nano_api_base";
    this.customBaseUrl = localStorage.getItem(this.storageKey) || "";
  }

  getBaseUrl() {
    if (this.customBaseUrl && this.customBaseUrl.trim()) {
      return this.customBaseUrl.replace(/\/+$/, "");
    }
    // Default: If served from any UI port in 10001-10100, default to backend port 10000.
    // If served directly from port 10000 (unified FastAPI), relative origin is used.
    if (typeof window !== "undefined" && window.location) {
      if (window.location.port && window.location.port !== "10000") {
        return `${window.location.protocol}//${window.location.hostname}:10000`;
      }
      return window.location.origin;
    }
    return "http://localhost:10000";
  }

  setBaseUrl(url) {
    this.customBaseUrl = (url || "").trim();
    if (this.customBaseUrl) {
      localStorage.setItem(this.storageKey, this.customBaseUrl);
    } else {
      localStorage.removeItem(this.storageKey);
    }
  }

  async request(path, options = {}) {
    const baseUrl = this.getBaseUrl();
    const url = `${baseUrl}${path.startsWith('/') ? path : '/' + path}`;
    
    const headers = {
      'Accept': 'application/json',
      ...(options.headers || {})
    };

    if (options.body && typeof options.body === 'object' && !(options.body instanceof FormData)) {
      headers['Content-Type'] = 'application/json';
      options.body = JSON.stringify(options.body);
    }

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), options.timeout || 900000);
      
      const response = await fetch(url, {
        ...options,
        headers,
        signal: controller.signal
      });
      clearTimeout(timeoutId);

      if (!response.ok) {
        let errMessage = `HTTP error ${response.status}: ${response.statusText}`;
        try {
          const errData = await response.json();
          if (errData && errData.detail) {
            errMessage = typeof errData.detail === 'string' ? errData.detail : JSON.stringify(errData.detail);
          }
        } catch (_) {}
        throw new Error(errMessage);
      }

      const contentType = response.headers.get("content-type");
      if (contentType && contentType.includes("application/json")) {
        return await response.json();
      }
      return await response.blob();
    } catch (err) {
      console.error(`API call to ${url} failed:`, err);
      throw err;
    }
  }

  async getHealth() {
    return this.request("/health", { method: "GET", timeout: 5000 });
  }

  async getHardwareStatus() {
    return this.request("/api/hardware", { method: "GET", timeout: 5000 });
  }

  async getModels() {
    return this.request("/api/models", { method: "GET", timeout: 5000 });
  }

  async getSystemHardware() {
    return this.request("/api/system", { method: "GET", timeout: 5000 });
  }

  async getPresets() {
    return this.request("/api/presets", { method: "GET", timeout: 5000 });
  }

  async optimizePrompt(prompt, style = "photorealistic", negativePrompt = "", aspectRatio = null) {
    return this.request("/api/optimize", {
      method: "POST",
      body: {
        prompt,
        style,
        negative_prompt: negativePrompt || null,
        aspect_ratio: aspectRatio || null
      }
    });
  }

  async generateImage(params) {
    return this.request("/api/generate", {
      method: "POST",
      body: {
        prompt: params.prompt,
        style: params.style || "photorealistic",
        negative_prompt: params.negativePrompt || "",
        aspect_ratio: params.aspectRatio || "1:1",
        steps: params.steps || 15,
        guidance_scale: params.guidanceScale || 7.5,
        seed: params.seed !== undefined && params.seed !== null && params.seed !== "" ? parseInt(params.seed, 10) : null,
        auto_optimize: params.autoOptimize !== false,
        run_qa: params.runQa !== false,
        session_id: params.sessionId || params.session_id || null,
        image_sources: params.imageSources || params.image_sources || null
      },
      timeout: 900000
    });
  }

  async editImage(params) {
    return this.request("/api/edit", {
      method: "POST",
      body: {
        image_source: params.imageSource,
        image_sources: params.imageSources || params.image_sources || null,
        mask_source: params.maskSource || null,
        prompt: params.prompt || null,
        edit_mode: params.editMode || "transform",
        filter_preset: params.filterPreset || null,
        brightness: params.brightness !== undefined ? parseFloat(params.brightness) : 1.0,
        contrast: params.contrast !== undefined ? parseFloat(params.contrast) : 1.0,
        saturation: params.saturation !== undefined ? parseFloat(params.saturation) : 1.0,
        sharpness: params.sharpness !== undefined ? parseFloat(params.sharpness) : 1.0,
        blur: params.blur !== undefined ? parseFloat(params.blur) : 0.0,
        vignette: params.vignette !== undefined ? parseFloat(params.vignette) : 0.0,
        gamma: params.gamma !== undefined ? parseFloat(params.gamma) : 1.0,
        strength: params.strength !== undefined ? parseFloat(params.strength) : 0.65,
        run_qa: params.runQa !== false,
        session_id: params.sessionId || params.session_id || null
      },
      timeout: 900000
    });
  }

  async getSessions() {
    return this.request("/api/sessions", { method: "GET", timeout: 8000 });
  }

  async createSession(title = null) {
    return this.request("/api/sessions", {
      method: "POST",
      body: title ? { title } : {}
    });
  }

  async getSession(sessionId) {
    return this.request(`/api/sessions/${encodeURIComponent(sessionId)}`, { method: "GET", timeout: 8000 });
  }

  async updateSession(sessionId, data = {}) {
    return this.request(`/api/sessions/${encodeURIComponent(sessionId)}`, {
      method: "PUT",
      body: data
    });
  }

  async renameSession(sessionId, title) {
    return this.updateSession(sessionId, { title });
  }

  async deleteSession(sessionId) {
    return this.request(`/api/sessions/${encodeURIComponent(sessionId)}`, { method: "DELETE" });
  }

  async auditImageQuality(imageSource) {
    return this.request("/api/qa", {
      method: "POST",
      body: { image_source: imageSource },
      timeout: 15000
    });
  }

  async getHistory() {
    return this.request("/api/history", { method: "GET", timeout: 8000 });
  }

  async clearCache() {
    return this.request("/api/cache/clear", { method: "POST", timeout: 15000 });
  }

  getImageUrl(filename) {
    if (!filename) return "";
    const baseUrl = this.getBaseUrl();
    return `${baseUrl}/api/image/${encodeURIComponent(filename)}`;
  }
}

// Export singleton instance
const api = new ApiClient();
if (typeof module !== "undefined" && module.exports) {
  module.exports = { ApiClient, api };
}
