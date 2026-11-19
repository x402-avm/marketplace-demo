/**
 * Gemini Nano & Banana - Image Gallery & History Store
 * Handles caching generated images, syncing with backend history, lightbox preview, and downloads.
 */

class GalleryStore {
  constructor(options = {}) {
    this.storageKey = "gemini_nano_gallery_history";
    this.container = typeof document !== 'undefined' ? document.getElementById(options.gridId || "galleryGrid") : null;
    this.filter = "all"; // 'all', 'gen', 'edit'
    this.items = this.loadLocal();
  }

  loadLocal() {
    try {
      const data = localStorage.getItem(this.storageKey);
      return data ? JSON.parse(data) : [];
    } catch (_) {
      return [];
    }
  }

  saveLocal() {
    try {
      // Store compact representation to stay well within 5MB localStorage quota
      const compactItems = this.items.slice(0, 50).map(item => {
        let saveUrl = item.url;
        // If url is a large base64 string and filename exists, store backend endpoint
        if (saveUrl && typeof saveUrl === 'string' && saveUrl.startsWith("data:") && item.filename) {
          const baseUrl = (typeof window !== 'undefined' && window.api) ? window.api.getBaseUrl() : "";
          saveUrl = `${baseUrl}/api/image/${item.filename}`;
        }
        return {
          ...item,
          url: saveUrl,
          // Omit massive raw originalUrl from local storage if filename exists or length > 5000
          originalUrl: (item.originalUrl && item.originalUrl.startsWith("data:") && item.originalUrl.length > 5000) ? null : item.originalUrl
        };
      });
      localStorage.setItem(this.storageKey, JSON.stringify(compactItems));
    } catch (e) {
      console.warn("Failed to persist gallery to localStorage:", e);
    }
  }

  addItem(item) {
    // Expected item: { id, type: 'gen'|'edit', url, filename, prompt, timestamp, qaReport, originalUrl }
    const newItem = {
      id: item.id || `img_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`,
      type: item.type || (item.filename && item.filename.startsWith("edit") ? "edit" : "gen"),
      url: item.url,
      filename: item.filename || "image.png",
      prompt: item.prompt || "Generated Artwork",
      timestamp: item.timestamp || Date.now(),
      qaReport: item.qaReport || null,
      originalUrl: item.originalUrl || null
    };

    // Prepend
    this.items.unshift(newItem);
    this.saveLocal();
    this.render();
    return newItem;
  }

  removeItem(id) {
    this.items = this.items.filter(item => item.id !== id);
    this.saveLocal();
    this.render();
  }

  clearAll() {
    if (typeof window !== 'undefined' && window.confirm && !window.confirm("Clear all items from creation gallery history?")) {
      return;
    }
    this.items = [];
    localStorage.removeItem(this.storageKey);
    this.render();
  }

  setFilter(filter) {
    this.filter = filter;
    this.render();
  }

  async syncWithBackend(apiInstance) {
    try {
      const res = await apiInstance.getHistory();
      if (res && res.images && Array.isArray(res.images)) {
        res.images.forEach(backendImg => {
          const exists = this.items.some(item => item.filename === backendImg.filename);
          if (!exists) {
            const isEdit = backendImg.filename.startsWith("edit_");
            this.items.push({
              id: `be_${backendImg.filename}`,
              type: isEdit ? "edit" : "gen",
              url: apiInstance.getImageUrl(backendImg.filename),
              filename: backendImg.filename,
              prompt: isEdit ? "Edited Masterpiece" : "AI Generated Artwork",
              timestamp: backendImg.created_at * 1000,
              qaReport: null
            });
          }
        });
        // Sort descending by timestamp
        this.items.sort((a, b) => b.timestamp - a.timestamp);
        this.saveLocal();
        this.render();
      }
    } catch (err) {
      console.warn("Backend history sync skipped:", err.message);
    }
  }

  render() {
    if (!this.container) return;
    
    let filtered = this.items;
    if (this.filter === "gen") {
      filtered = this.items.filter(item => item.type === "gen");
    } else if (this.filter === "edit") {
      filtered = this.items.filter(item => item.type === "edit");
    }

    if (filtered.length === 0) {
      this.container.innerHTML = `
        <div style="grid-column: 1 / -1; text-align: center; padding: 4rem 1rem; color: var(--text-muted);">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="margin-bottom: 1rem; opacity: 0.5;">
            <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
            <circle cx="8.5" cy="8.5" r="1.5"/>
            <polyline points="21 15 16 10 5 21"/>
          </svg>
          <p style="font-size: 1rem; font-weight: 500;">No images in gallery yet</p>
          <p style="font-size: 0.85rem; margin-top: 0.25rem;">Generate an image or edit one in the studio to populate your gallery.</p>
        </div>
      `;
      return;
    }

    this.container.innerHTML = filtered.map(item => {
      const safePrompt = (item.prompt || "Artwork").replace(/"/g, '&quot;').replace(/'/g, '&#39;');
      return `
      <div class="gallery-card" data-id="${item.id}">
        <div class="gallery-card-thumb-wrap">
          <img class="gallery-card-img" src="${item.url}" alt="${safePrompt}" loading="lazy" onclick="gallery.openLightbox('${item.id}')" />
          <span style="position: absolute; top: 0.5rem; left: 0.5rem; font-size: 0.68rem; font-weight: 600; text-transform: uppercase; padding: 0.15rem 0.45rem; border-radius: var(--radius-pill); background: rgba(0,0,0,0.65); backdrop-filter: blur(4px); color: ${item.type === 'edit' ? 'var(--banana-yellow)' : 'var(--gemini-purple)'};">
            ${item.type === 'edit' ? 'Studio Edit' : 'Text-to-Image'}
          </span>
        </div>
        <div class="gallery-card-info">
          <p class="gallery-card-prompt" title="${safePrompt}">${safePrompt}</p>
          <span style="font-size: 0.7rem; color: var(--text-muted);">${new Date(item.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
          <div class="gallery-card-actions">
            <button class="btn-secondary" style="flex: 1; padding: 0.35rem 0.5rem; font-size: 0.75rem;" onclick="gallery.sendToStudio('${item.id}')" title="Edit in Studio">
              Studio
            </button>
            ${item.originalUrl ? `
              <button class="btn-secondary" style="flex: 1; padding: 0.35rem 0.5rem; font-size: 0.75rem;" onclick="gallery.openComparison('${item.id}')" title="Side-by-Side Comparison">
                Compare
              </button>
            ` : ''}
            <button class="btn-secondary" style="padding: 0.35rem 0.5rem; font-size: 0.75rem;" onclick="gallery.downloadItem('${item.id}')" title="Download">
              &darr;
            </button>
            <button class="btn-secondary" style="padding: 0.35rem 0.5rem; font-size: 0.75rem; color: var(--color-error);" onclick="gallery.removeItem('${item.id}')" title="Delete">
              &times;
            </button>
          </div>
        </div>
      </div>
      `;
    }).join("");
  }

  openLightbox(id) {
    const item = this.items.find(i => i.id === id);
    if (!item) return;

    const modal = document.getElementById("lightboxModal");
    const img = document.getElementById("lightboxImg");
    const caption = document.getElementById("lightboxCaption");
    const dlBtn = document.getElementById("lightboxDownloadBtn");

    if (img) img.src = item.url;
    if (caption) caption.textContent = item.prompt;
    if (dlBtn) dlBtn.onclick = () => this.download(item.url, item.filename);

    if (modal) modal.classList.add("active");
  }

  sendToStudio(id) {
    const item = this.items.find(i => i.id === id);
    if (item && typeof window !== 'undefined' && window.app) {
      window.app.sendToStudio(item.url);
    }
  }

  openComparison(id) {
    const item = this.items.find(i => i.id === id);
    if (item && item.originalUrl && typeof window !== 'undefined' && window.app) {
      window.app.openComparison(item.originalUrl, item.url);
    }
  }

  downloadItem(id) {
    const item = this.items.find(i => i.id === id);
    if (item) {
      this.download(item.url, item.filename);
    }
  }

  download(url, filename = "gemini_nano_output.png") {
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }
}

// Export for tests & module loaders
if (typeof module !== "undefined" && module.exports) {
  module.exports = { GalleryStore };
}
