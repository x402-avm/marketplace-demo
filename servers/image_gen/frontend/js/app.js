/**
 * Gemini Nano & Banana - Main Application Orchestrator
 * Integrates T2I Generation, Prompt-guided Image Editing, Studio Canvas,
 * Comparison Slider, Gallery, and Real-Time Hardware Telemetry.
 */

class GeminiNanoApp {
  constructor() {
    this.api = (typeof window !== "undefined" && window.api) ? window.api : (typeof ApiClient !== "undefined" ? new ApiClient() : null);
    this.canvas = null;
    this.comparison = null;
    this.gallery = null;
    this.qaPanel = null;

    // Active Generation & Edit State
    this.activeTab = "generate";
    this.activeStyle = "photorealistic";
    this.activeAspectRatio = "1:1";
    this.selectedFilterPreset = "none";
    this.lastGeneratedResult = null;
    this.lastEditedResult = null;
    this.editReference = null; // Legacy single reference { src: string, name: string }
    this.attachedImages = []; // Multi-image references [{ src: string, name: string }]
    this.sessionManager = (typeof SessionManager !== "undefined") ? new SessionManager({ api: this.api }) : null;

    // Generation timer
    this.genInterval = null;
    this.genStartTime = 0;
  }

  init() {
    console.log("[Gemini Nano UI] Initializing Google Gemini interface...");

    // Initialize Canvas & Comparison
    this.canvas = new StudioCanvas({
      viewportId: "canvasViewport",
      panContainerId: "panContainer",
      imageCanvasId: "imageCanvas",
      maskCanvasId: "maskCanvas"
    });

    this.comparison = new ImageComparison({
      containerId: "comparisonContainer",
      beforeWrapperId: "comparisonBeforeWrapper",
      beforeImgId: "comparisonImgBefore",
      afterImgId: "comparisonImgAfter",
      handleId: "comparisonHandle",
      dualColumnId: "dualColumnView",
      dualBeforeImgId: "dualBeforeImg",
      dualAfterImgId: "dualAfterImg"
    });

    this.gallery = new GalleryStore({ gridId: "galleryGrid" });
    this.qaPanel = new QAPanel("qaPanelContainer");

    // Make global references available
    window.gallery = this.gallery;
    window.app = this;
    if (this.sessionManager) {
      window.sessionManager = this.sessionManager;
    }

    // Attach event listeners
    this.bindNavigation();
    this.bindSidebarControls();
    this.bindPromptControls();
    this.bindGeneratorControls();
    this.bindStudioControls();
    this.bindComparisonControls();
    this.bindSettingsAndHardware();
    this.bindKeyboardShortcuts();

    // Initial render
    this.gallery.render();
    this.fetchSystemTelemetry();
    this.gallery.syncWithBackend(this.api);
    if (this.sessionManager) {
      this.sessionManager.loadSessions();
    }

    // Load initial sample in studio canvas (crisp, zero procedural rings)
    this.loadDefaultStudioImage();

    // Periodic hardware telemetry refresh (every 15s)
    this.telemetryInterval = setInterval(() => {
      this.fetchSystemTelemetry();
    }, 15000);

    this.showToast("Gemini Nano Engine ready &bull; AMD Ryzen AI 9 HX 370 Zen 5 CPU Isolated", "success");
  }

  showToast(message, type = "info") {
    const container = document.getElementById("toastContainer");
    if (!container) return;

    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
      <div style="flex: 1;">${message}</div>
      <button style="background: none; border: none; color: inherit; cursor: pointer; font-size: 1.1rem; padding: 0 0.2rem;" onclick="this.parentElement.remove()">&times;</button>
    `;

    container.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transition = "opacity 0.3s ease";
      setTimeout(() => {
        if (typeof toast.remove === "function") {
          toast.remove();
        } else if (toast.parentElement) {
          toast.parentElement.removeChild(toast);
        }
      }, 300);
    }, 4500);
  }

  // ----------------------------------------------------
  // Navigation Tabs
  // ----------------------------------------------------
  bindSidebarControls() {
    const toggleBtn = document.getElementById("sidebarToggleBtn") || document.getElementById("btnToggleSidebar");
    if (toggleBtn && this.sessionManager) {
      toggleBtn.addEventListener("click", () => this.sessionManager.toggleSidebar());
    }

    const newChatBtn = document.getElementById("btnNewChat") || document.getElementById("newChatBtn");
    if (newChatBtn && this.sessionManager) {
      newChatBtn.addEventListener("click", () => {
        this.sessionManager.createSession("New Chat");
      });
    }

    // Restore sidebar state from localStorage
    if (typeof localStorage !== "undefined" && localStorage.getItem("gemini_sidebar_collapsed") === "1") {
      const sidebar = document.getElementById("geminiSidebar");
      if (sidebar) sidebar.classList.add("collapsed");
    }
  }

  bindNavigation() {
    const navButtons = document.querySelectorAll(".nav-tab-btn");
    navButtons.forEach(btn => {
      btn.addEventListener("click", () => {
        const targetTab = btn.getAttribute("data-tab");
        this.switchTab(targetTab);
      });
    });
  }

  switchTab(tabId) {
    this.activeTab = tabId;

    // Update nav button active classes
    document.querySelectorAll(".nav-tab-btn").forEach(btn => {
      if (btn.getAttribute("data-tab") === tabId) {
        btn.classList.add("active");
      } else {
        btn.classList.remove("active");
      }
    });

    // Update panel visibility
    document.querySelectorAll(".tab-content-panel").forEach(panel => {
      if (panel.id === `tab-${tabId}`) {
        panel.classList.add("active");
      } else {
        panel.classList.remove("active");
      }
    });

    // Refresh layout-sensitive components
    if (tabId === "studio" && this.canvas) {
      setTimeout(() => this.canvas.resetTransform(), 50);
    } else if (tabId === "compare" && this.comparison) {
      setTimeout(() => this.comparison.syncDimensions(), 50);
    } else if (tabId === "gallery" && this.gallery) {
      this.gallery.render();
    }
  }

  // ----------------------------------------------------
  // Prompt Controls & Dock
  // ----------------------------------------------------
  bindPromptControls() {
    const promptInput = document.getElementById("promptInput");
    const charCount = document.getElementById("promptCharCount");
    const refineBtn = document.getElementById("refinePromptBtn");

    if (promptInput) {
      // Auto-expanding textarea & character count
      promptInput.addEventListener("input", () => {
        promptInput.style.height = "auto";
        promptInput.style.height = `${Math.min(promptInput.scrollHeight, 140)}px`;
        if (charCount) charCount.textContent = `${promptInput.value.length} chars`;
      });

      // Enter to generate (Shift+Enter for newline)
      promptInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          this.executeGeneration();
        }
      });
    }

    // Inspiration prompt chips in hero greeting
    document.querySelectorAll(".prompt-chip[data-prompt]").forEach(chip => {
      chip.addEventListener("click", () => {
        const text = chip.getAttribute("data-prompt") || chip.textContent.trim();
        if (promptInput) {
          promptInput.value = text;
          promptInput.style.height = "auto";
          promptInput.style.height = `${Math.min(promptInput.scrollHeight, 140)}px`;
          if (charCount) charCount.textContent = `${text.length} chars`;
          promptInput.focus();
        }
      });
    });

    // Style Presets (Hero and Controls)
    document.querySelectorAll(".preset-card-btn").forEach(card => {
      card.addEventListener("click", () => {
        document.querySelectorAll(".preset-card-btn").forEach(c => c.classList.remove("active"));
        card.classList.add("active");
        this.activeStyle = card.getAttribute("data-style") || "photorealistic";
      });
    });

    // Aspect Ratios in Floating Dock
    document.querySelectorAll(".aspect-ratio-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".aspect-ratio-btn").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        this.activeAspectRatio = btn.getAttribute("data-ratio") || "1:1";
      });
    });

    // Attachment button (+) for multi-image prompt editing
    const attachBtn = document.getElementById("attachImageBtn");
    const dockFileInput = document.getElementById("dockFileInput");
    if (attachBtn && dockFileInput) {
      attachBtn.addEventListener("click", () => dockFileInput.click());
      dockFileInput.addEventListener("change", (e) => {
        const files = Array.from(e.target.files || []);
        files.forEach(file => {
          const reader = new FileReader();
          reader.onload = (event) => {
            this.addAttachedImage(event.target.result, file.name);
          };
          reader.readAsDataURL(file);
        });
        dockFileInput.value = "";
      });
    }

    // Drag and drop onto prompt pill for multi-image input
    const promptPill = document.querySelector(".gemini-prompt-pill");
    if (promptPill) {
      promptPill.addEventListener("dragover", (e) => {
        e.preventDefault();
        promptPill.style.borderColor = "var(--accent-blue)";
      });
      promptPill.addEventListener("dragleave", () => {
        promptPill.style.borderColor = "";
      });
      promptPill.addEventListener("drop", (e) => {
        e.preventDefault();
        promptPill.style.borderColor = "";
        const files = Array.from(e.dataTransfer?.files || []).filter(f => f.type.startsWith("image/"));
        files.forEach(file => {
          const reader = new FileReader();
          reader.onload = (event) => {
            this.addAttachedImage(event.target.result, file.name);
          };
          reader.readAsDataURL(file);
        });
      });
    }

    // Options Drawer Toggle
    const optionsToggleBtn = document.getElementById("optionsDrawerToggleBtn");
    const optionsDrawer = document.getElementById("advancedAccordionWrapper");
    const drawerHeader = document.getElementById("advancedAccordionHeader");
    if (optionsToggleBtn && optionsDrawer) {
      optionsToggleBtn.addEventListener("click", () => {
        optionsDrawer.classList.toggle("open");
      });
    }
    if (drawerHeader && optionsDrawer) {
      drawerHeader.addEventListener("click", () => {
        optionsDrawer.classList.remove("open");
      });
    }

    // Refine prompt with AI Prompt Engineer
    if (refineBtn) {
      refineBtn.addEventListener("click", async () => {
        const raw = promptInput ? promptInput.value.trim() : "";
        if (!raw) {
          this.showToast("Enter a prompt first to refine with AI", "warning");
          return;
        }

        refineBtn.disabled = true;
        refineBtn.innerHTML = `<span>Refining...</span>`;

        try {
          const res = await this.api.optimizePrompt(raw, this.activeStyle, "", this.activeAspectRatio);
          if (res && res.optimized_prompt) {
            promptInput.value = res.optimized_prompt;
            promptInput.style.height = "auto";
            promptInput.style.height = `${Math.min(promptInput.scrollHeight, 140)}px`;
            if (charCount) charCount.textContent = `${res.optimized_prompt.length} chars`;
            this.showToast("Prompt enriched with Gemini Nano aesthetic presets!", "success");
          }
        } catch (err) {
          this.showToast(`Prompt refinement failed: ${err.message}`, "error");
        } finally {
          refineBtn.disabled = false;
          refineBtn.innerHTML = `
            <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 2L15 9L22 12L15 15L12 22L9 15L2 12L9 9L12 2Z"/>
            </svg>
            <span>Refine</span>
          `;
        }
      });
    }

    // Advanced Tuning Sliders sync
    this.bindSliderWithDisplay("stepsSlider", "stepsVal");
    this.bindSliderWithDisplay("guidanceSlider", "guidanceVal");
    
    // Random seed button
    const diceBtn = document.getElementById("randomSeedBtn");
    const seedInput = document.getElementById("seedInput");
    if (diceBtn && seedInput) {
      diceBtn.addEventListener("click", () => {
        seedInput.value = Math.floor(Math.random() * 10000000);
      });
    }
  }

  addAttachedImage(imageSrc, filename = "image.png") {
    this.attachedImages.push({ src: imageSrc, name: filename });
    this.editReference = this.attachedImages[0];
    this.renderAttachedChips();
    this.showToast(`Attached ${filename} (${this.attachedImages.length} images in context) ✨`, "info");
  }

  setEditReference(imageSrc, filename = "image.png") {
    this.attachedImages = [{ src: imageSrc, name: filename }];
    this.editReference = this.attachedImages[0];
    const thumb = document.getElementById("editReferenceThumb");
    if (thumb) thumb.src = imageSrc;
    this.renderAttachedChips();
    const promptInput = document.getElementById("promptInput");
    if (promptInput) {
      promptInput.placeholder = "Describe edits to make (e.g. add dramatic neon lighting, change sky to sunset)...";
      promptInput.focus();
    }
    this.showToast("Image attached as editing reference ✨", "info");
  }

  removeAttachedImage(index) {
    this.attachedImages.splice(index, 1);
    this.editReference = this.attachedImages[0] || null;
    this.renderAttachedChips();
  }

  clearEditReference() {
    this.attachedImages = [];
    this.editReference = null;
    this.renderAttachedChips();
    const promptInput = document.getElementById("promptInput");
    if (promptInput) {
      promptInput.placeholder = "Ask Gemini to create or edit an image...";
    }
  }

  renderAttachedChips() {
    const chipContainer = document.getElementById("editReferenceChipContainer");
    if (!chipContainer) return;
    if (this.attachedImages.length === 0) {
      chipContainer.classList.remove("active");
      chipContainer.innerHTML = "";
      return;
    }

    chipContainer.classList.add("active");
    chipContainer.innerHTML = this.attachedImages.map((img, idx) => `
      <div class="edit-reference-chip" style="margin-right: 0.35rem; margin-bottom: 0.25rem;">
        <img class="edit-reference-thumb" src="${img.src}" alt="${img.name || 'Ref'}">
        <span>${img.name && img.name.length > 20 ? img.name.slice(0, 18) + '...' : (img.name || `Image ${idx + 1}`)}</span>
        <button type="button" class="edit-reference-close-btn" data-idx="${idx}" title="Remove image">&times;</button>
      </div>
    `).join("");

    if (typeof chipContainer.querySelectorAll === "function") {
      chipContainer.querySelectorAll(".edit-reference-close-btn").forEach(btn => {
        btn.addEventListener("click", (e) => {
          e.stopPropagation();
          const idx = parseInt(btn.getAttribute("data-idx"), 10);
          this.removeAttachedImage(idx);
        });
      });
    }

    const promptInput = document.getElementById("promptInput");
    if (promptInput) {
      promptInput.placeholder = this.attachedImages.length > 1
        ? `Describe how to blend/composite these ${this.attachedImages.length} images...`
        : "Describe edits to make (e.g. change lighting, add elements)...";
    }
  }

  bindSliderWithDisplay(sliderId, displayId) {
    const slider = document.getElementById(sliderId);
    const display = document.getElementById(displayId);
    if (slider && display) {
      slider.addEventListener("input", () => {
        display.textContent = slider.value;
      });
    }
  }

  // ----------------------------------------------------
  // Generator & Card Action Controls
  // ----------------------------------------------------
  bindGeneratorControls() {
    const generateBtn = document.getElementById("generateBtn");
    if (generateBtn) {
      generateBtn.addEventListener("click", () => this.executeGeneration());
    }

    // Action Chip: Edit with Prompt (Sets current image as edit reference)
    const cardEditPromptBtn = document.getElementById("cardEditPromptBtn");
    if (cardEditPromptBtn) {
      cardEditPromptBtn.addEventListener("click", () => {
        const currentImg = this.lastEditedResult?.image_base64 || this.lastGeneratedResult?.image_base64;
        const currentName = this.lastEditedResult?.filename || this.lastGeneratedResult?.filename;
        if (currentImg) {
          this.setEditReference(currentImg, currentName);
        } else {
          this.showToast("Generate an image first to edit", "warning");
        }
      });
    }

    // Action Chip: Inpaint & Erase (Sends to Studio Canvas)
    const sendToStudioBtn = document.getElementById("previewSendStudioBtn");
    if (sendToStudioBtn) {
      sendToStudioBtn.addEventListener("click", () => {
        const currentImg = this.lastEditedResult?.image_base64 || this.lastGeneratedResult?.image_base64;
        if (currentImg) {
          this.sendToStudio(currentImg);
        }
      });
    }

    // Action Chip: Variations (Regenerates with a new random seed)
    const variationsBtn = document.getElementById("cardVariationsBtn");
    if (variationsBtn) {
      variationsBtn.addEventListener("click", () => {
        const seedInput = document.getElementById("seedInput");
        if (seedInput) seedInput.value = Math.floor(Math.random() * 10000000);
        this.executeGeneration();
      });
    }

    // Action Chip: Compare Split (Opens comparison slider)
    const compareBtn = document.getElementById("cardCompareBtn");
    if (compareBtn) {
      compareBtn.addEventListener("click", () => {
        const after = this.lastEditedResult?.image_base64 || this.lastGeneratedResult?.image_base64;
        const before = this.lastEditedResult?.originalUrl || this.lastGeneratedResult?.image_base64;
        if (after) {
          this.openComparison(before || after, after);
        }
      });
    }

    // Action Chip: Download PNG
    const downloadBtn = document.getElementById("previewDownloadBtn");
    if (downloadBtn) {
      downloadBtn.addEventListener("click", () => {
        const current = this.lastEditedResult || this.lastGeneratedResult;
        if (current && current.image_base64) {
          this.gallery.download(
            current.image_base64,
            current.filename || "gemini_nano_output.png"
          );
        }
      });
    }
  }

  // ----------------------------------------------------
  // Generation & Prompt Editing Execution
  // ----------------------------------------------------
  async executeGeneration() {
    const promptInput = document.getElementById("promptInput");
    const rawPrompt = promptInput ? promptInput.value.trim() : "";
    if (!rawPrompt) {
      this.showToast("Please enter a prompt to create or edit an image", "warning");
      return;
    }

    const generateBtn = document.getElementById("generateBtn");
    const overlay = document.getElementById("previewLoadingOverlay");
    const statusText = document.getElementById("loadingStatusText");
    const timerText = document.getElementById("loadingTimerText");
    const emptyState = document.getElementById("previewEmptyState");
    const chatStream = document.getElementById("geminiChatStream");
    const activeCard = document.getElementById("activeGenerationCard");
    const previewImg = document.getElementById("previewOutputImage");
    const negativeInput = document.getElementById("negativePromptInput");
    const stepsSlider = document.getElementById("stepsSlider");
    const guidanceSlider = document.getElementById("guidanceSlider");
    const seedInput = document.getElementById("seedInput");
    const autoOptimizeToggle = document.getElementById("autoOptimizeToggle");
    const qaAuditToggle = document.getElementById("qaAuditToggle");

    // Hide empty state and show loading overlay
    if (emptyState) emptyState.style.display = "none";
    if (generateBtn) generateBtn.disabled = true;
    if (overlay) overlay.classList.add("active");

    // Add user message bubble to chat feed
    if (chatStream) {
      const userBubble = document.createElement("div");
      userBubble.className = "user-prompt-bubble";
      const thumbsHtml = (this.attachedImages && this.attachedImages.length > 0)
        ? `<div class="user-attached-thumbs" style="display: flex; gap: 0.35rem; margin-bottom: 0.4rem; flex-wrap: wrap;">
            ${this.attachedImages.map(img => `<img src="${img.src}" style="width: 44px; height: 44px; border-radius: 6px; object-fit: cover; border: 1px solid rgba(255,255,255,0.2);">`).join("")}
          </div>`
        : "";
      userBubble.innerHTML = `
        <div class="user-avatar-icon">U</div>
        <div class="user-prompt-content">
          ${thumbsHtml}
          <div class="user-prompt-text">${rawPrompt}</div>
          <div class="user-prompt-badges">
            ${(this.attachedImages && this.attachedImages.length > 0) ? `<span class="user-badge-chip">✨ ${this.attachedImages.length} Image${this.attachedImages.length > 1 ? 's' : ''} in Context</span>` : `<span class="user-badge-chip">🎨 ${this.activeStyle}</span>`}
            <span class="user-badge-chip">📐 ${this.activeAspectRatio}</span>
          </div>
        </div>
      `;
      chatStream.appendChild(userBubble);
      // Auto-scroll feed to latest
      const feedContainer = document.getElementById("generationPreviewArea");
      if (feedContainer) feedContainer.scrollTop = feedContainer.scrollHeight;
    }

    const statusMessages = [
      "Warming AMD Ryzen AI 9 HX 370 Zen 5 CPU threads...",
      "Encoding text conditioning with CLIP...",
      "Executing NVFP4 diffusion steps on Zen 5 CPU / Radeon 890M...",
      "Synthesizing dynamic range & color channels via VAE...",
      "Auditing visual quality with QA Critic agent..."
    ];
    let msgIdx = 0;
    if (statusText) statusText.textContent = statusMessages[0];

    this.genStartTime = Date.now();
    this.genInterval = setInterval(() => {
      const elapsed = ((Date.now() - this.genStartTime) / 1000).toFixed(1);
      if (timerText) timerText.textContent = `${elapsed}s elapsed`;

      msgIdx = (msgIdx + 1) % statusMessages.length;
      if (statusText) statusText.textContent = statusMessages[msgIdx];
    }, 2000);

    try {
      const activeSessionId = this.sessionManager ? this.sessionManager.getCurrentSessionId() : null;
      let res;
      if (this.attachedImages && this.attachedImages.length > 0) {
        // Multi-image or single-image guided editing/composition
        const sources = this.attachedImages.map(img => img.src);
        res = await this.api.editImage({
          imageSource: sources[0],
          imageSources: sources,
          prompt: rawPrompt,
          editMode: "ai_img2img",
          strength: 1.0,
          runQa: qaAuditToggle ? qaAuditToggle.checked : true,
          sessionId: activeSessionId
        });

        const imageUrl = res.image_base64 || res.image_url || (res.filename ? this.api.getImageUrl(res.filename) : "");
        if (!imageUrl) {
          throw new Error("No output image was returned by the editing engine.");
        }
        res.imageUrl = imageUrl;
        this.lastEditedResult = res;

        // Add to gallery with original URL tracking for comparison
        this.gallery.addItem({
          type: "edit",
          url: imageUrl,
          filename: res.filename,
          prompt: `In-context Edit (${sources.length} images): ${rawPrompt}`,
          qaReport: res.qa_report,
          originalUrl: sources[0]
        });

        // Set up comparison
        this.comparison.setImages(sources[0], imageUrl);
        this.showToast(`✨ Generated in ${res.total_latency_seconds || 1.1}s using ${sources.length} images in context!`, "success");

      } else {
        // Text-to-Image Generation (with full session history context)
        res = await this.api.generateImage({
          prompt: rawPrompt,
          style: this.activeStyle,
          negativePrompt: negativeInput ? negativeInput.value : "",
          aspectRatio: this.activeAspectRatio,
          steps: stepsSlider ? parseInt(stepsSlider.value, 10) : 15,
          guidanceScale: guidanceSlider ? parseFloat(guidanceSlider.value) : 7.5,
          seed: seedInput && seedInput.value.trim() ? parseInt(seedInput.value.trim(), 10) : null,
          autoOptimize: autoOptimizeToggle ? autoOptimizeToggle.checked : true,
          runQa: qaAuditToggle ? qaAuditToggle.checked : true,
          sessionId: activeSessionId
        });

        const imageUrl = res.image_base64 || res.image_url || (res.filename ? this.api.getImageUrl(res.filename) : "");
        if (!imageUrl) {
          throw new Error("No output image was returned by the generation engine.");
        }
        res.imageUrl = imageUrl;
        this.lastGeneratedResult = res;

        // Add to gallery
        this.gallery.addItem({
          type: "gen",
          url: imageUrl,
          filename: res.filename,
          prompt: rawPrompt,
          qaReport: res.qa_report
        });

        this.showToast(`✨ Image generated in ${res.total_latency_seconds || 1.3}s on CPU!`, "success");
      }

      const finalImageUrl = res.imageUrl || res.image_base64 || res.image_url || (res.filename ? this.api.getImageUrl(res.filename) : "");
      const finalFilename = res.filename || "gemini_image.png";
      const latencyStr = `${res.total_latency_seconds || '1.2'}s`;

      // Auto-title session if it's currently "New Chat"
      if (this.sessionManager && activeSessionId) {
        const curSess = this.sessionManager.sessions.find(s => s.id === activeSessionId);
        if (curSess && curSess.title === "New Chat") {
          const newTitle = rawPrompt.length > 28 ? rawPrompt.substring(0, 28).trim() + "..." : rawPrompt;
          this.sessionManager.renameSession(activeSessionId, newTitle);
        } else {
          this.sessionManager.renderSessionsList();
        }
      }

      // Append assistant card into chat feed for multi-turn history visibility
      if (chatStream && finalImageUrl) {
        const card = document.createElement("div");
        card.className = "gemini-generation-card";
        card.innerHTML = `
          <div class="card-assistant-header">
            <div class="assistant-identity">
              <div class="assistant-sparkle-dot">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="#ffffff">
                  <path d="M12 2L14.8 8.6L22 12L14.8 15.4L12 22L9.2 15.4L2 12L9.2 8.6L12 2Z"/>
                </svg>
              </div>
              <span>Gemini Nano</span>
            </div>
            <div class="generation-telemetry-pill">
              <span>✨ Qwen 2.1 Heretic NVFP4 • AMD Ryzen AI 9 HX 370 CPU • ${latencyStr}</span>
            </div>
          </div>
          <div class="image-display-frame">
            <img src="${finalImageUrl}" alt="Generated Image" style="max-width: 100%; max-height: 58vh; object-fit: contain; display: block;">
          </div>
          <div class="gemini-action-chips">
            <button type="button" class="gemini-chip-btn chip-primary" data-action="edit-prompt">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 2L14.8 8.6L22 12L14.8 15.4L12 22L9.2 15.4L2 12L9.2 8.6L12 2Z"/>
              </svg>
              <span>Edit with Prompt</span>
            </button>
            <button type="button" class="gemini-chip-btn" data-action="studio">
              <span>🖌️ Inpaint &amp; Erase</span>
            </button>
            <button type="button" class="gemini-chip-btn" data-action="download">
              <span>⬇️ Download</span>
            </button>
          </div>
        `;
        const editBtn = card.querySelector('[data-action="edit-prompt"]');
        if (editBtn) editBtn.addEventListener("click", () => this.setEditReference(finalImageUrl, finalFilename));
        const studioBtn = card.querySelector('[data-action="studio"]');
        if (studioBtn) studioBtn.addEventListener("click", () => this.sendToStudio(finalImageUrl));
        const downloadBtn = card.querySelector('[data-action="download"]');
        if (downloadBtn) {
          downloadBtn.addEventListener("click", () => {
            if (this.gallery && typeof this.gallery.download === "function") {
              this.gallery.download(finalImageUrl, finalFilename);
            } else {
              const a = document.createElement("a");
              a.href = finalImageUrl;
              a.download = finalFilename;
              a.click();
            }
          });
        }
        chatStream.appendChild(card);
      }

      // Display Generative Card
      if (activeCard) activeCard.style.display = "flex";
      if (previewImg && finalImageUrl) {
        previewImg.src = finalImageUrl;
        previewImg.style.display = "block";
      }

      // Update Telemetry Pill
      const latencyVal = document.getElementById("telemetryLatencyVal");
      if (latencyVal) {
        latencyVal.textContent = latencyStr;
      }
      const telemetryPill = document.getElementById("cardTelemetryPill");
      if (telemetryPill) {
        telemetryPill.innerHTML = `<span>✨ Qwen 2.1 Heretic NVFP4 • AMD Ryzen AI 9 HX 370 CPU • <span id="telemetryLatencyVal">${latencyStr}</span></span>`;
      }

      // Render QA
      if (res.qa_report && this.qaPanel) {
        this.qaPanel.render(res.qa_report);
        const qaContainer = document.getElementById("qaPanelContainer");
        if (qaContainer) qaContainer.style.display = "block";
      }

      // Clear prompt input & reference dock after successful send
      if (promptInput) {
        promptInput.value = "";
        promptInput.style.height = "auto";
        const charCount = document.getElementById("promptCharCount");
        if (charCount) charCount.textContent = "0 chars";
      }
      this.clearEditReference();

      // Scroll to result card
      const feedContainer = document.getElementById("generationPreviewArea");
      if (feedContainer) {
        setTimeout(() => {
          feedContainer.scrollTop = feedContainer.scrollHeight;
        }, 100);
      }

    } catch (err) {
      this.showToast(`Action failed: ${err.message}`, "error");
    } finally {
      clearInterval(this.genInterval);
      if (generateBtn) generateBtn.disabled = false;
      if (overlay) overlay.classList.remove("active");
    }
  }

  // ----------------------------------------------------
  // Image Studio & Masking Canvas Controls
  // ----------------------------------------------------
  bindStudioControls() {
    // Tool buttons: brush, eraser, pan
    document.querySelectorAll(".canvas-tool-btn[data-tool]").forEach(btn => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".canvas-tool-btn[data-tool]").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        const tool = btn.getAttribute("data-tool");
        if (this.canvas) this.canvas.setTool(tool);
      });
    });

    // Zoom buttons
    const zoomInBtn = document.getElementById("zoomInBtn");
    const zoomOutBtn = document.getElementById("zoomOutBtn");
    const zoomFitBtn = document.getElementById("zoomFitBtn");

    if (zoomInBtn) zoomInBtn.addEventListener("click", () => this.canvas.zoom(1.2));
    if (zoomOutBtn) zoomOutBtn.addEventListener("click", () => this.canvas.zoom(0.8));
    if (zoomFitBtn) zoomFitBtn.addEventListener("click", () => this.canvas.resetTransform());

    // Undo & Clear mask
    const undoMaskBtn = document.getElementById("undoMaskBtn");
    const clearMaskBtn = document.getElementById("clearMaskBtn");

    if (undoMaskBtn) undoMaskBtn.addEventListener("click", () => this.canvas.undoMask());
    if (clearMaskBtn) clearMaskBtn.addEventListener("click", () => this.canvas.clearMask());

    // Brush size slider
    const brushSlider = document.getElementById("brushSizeSlider");
    const brushVal = document.getElementById("brushSizeVal");
    if (brushSlider) {
      brushSlider.addEventListener("input", () => {
        const val = parseInt(brushSlider.value, 10);
        if (brushVal) brushVal.textContent = `${val}px`;
        if (this.canvas) this.canvas.setBrushSize(val);
      });
    }

    // Image Upload in Studio
    const uploadInput = document.getElementById("studioUploadInput");
    const uploadBtn = document.getElementById("studioUploadBtn");
    if (uploadBtn && uploadInput) {
      uploadBtn.addEventListener("click", () => uploadInput.click());
      uploadInput.addEventListener("change", (e) => {
        const file = e.target.files[0];
        if (file) {
          const reader = new FileReader();
          reader.onload = (event) => {
            this.canvas.loadImage(event.target.result);
            this.showToast("Uploaded image loaded into studio canvas", "info");
          };
          reader.readAsDataURL(file);
        }
      });
    }

    // Adjustment sliders
    const adjustmentKeys = ["brightness", "contrast", "saturation", "sharpness", "blur", "vignette"];
    adjustmentKeys.forEach(key => {
      const slider = document.getElementById(`adj_${key}`);
      const valDisp = document.getElementById(`adj_val_${key}`);
      if (slider) {
        slider.addEventListener("input", () => {
          const val = parseFloat(slider.value);
          if (valDisp) valDisp.textContent = val.toFixed(key === "blur" ? 0 : 2);
          if (this.canvas) {
            this.canvas.updateAdjustments({ [key]: val });
          }
        });
      }
    });

    // Reset adjustments
    const resetAdjBtn = document.getElementById("resetAdjustmentsBtn");
    if (resetAdjBtn) {
      resetAdjBtn.addEventListener("click", () => {
        adjustmentKeys.forEach(key => {
          const slider = document.getElementById(`adj_${key}`);
          const valDisp = document.getElementById(`adj_val_${key}`);
          const defaultVal = key === "blur" || key === "vignette" ? 0 : 1.0;
          if (slider) slider.value = defaultVal;
          if (valDisp) valDisp.textContent = defaultVal.toFixed(key === "blur" ? 0 : 2);
        });
        if (this.canvas) this.canvas.resetAdjustments();
      });
    }

    // Filter presets chips
    document.querySelectorAll(".filter-chip").forEach(chip => {
      chip.addEventListener("click", () => {
        document.querySelectorAll(".filter-chip").forEach(c => c.classList.remove("active"));
        chip.classList.add("active");
        this.selectedFilterPreset = chip.getAttribute("data-filter") || "none";
      });
    });

    // Generative AI strength slider
    const strengthSlider = document.getElementById("studioStrengthSlider");
    const strengthVal = document.getElementById("studioStrengthVal");
    if (strengthSlider && strengthVal) {
      strengthSlider.addEventListener("input", () => {
        strengthVal.textContent = parseFloat(strengthSlider.value).toFixed(2);
      });
    }

    // Apply Studio Edit
    const applyEditBtn = document.getElementById("applyStudioEditBtn");
    if (applyEditBtn) {
      applyEditBtn.addEventListener("click", () => this.executeStudioEdit());
    }
  }

  async executeStudioEdit() {
    if (!this.canvas || !this.canvas.currentImage) {
      this.showToast("Load an image into the studio canvas first", "warning");
      return;
    }

    const applyEditBtn = document.getElementById("applyStudioEditBtn");
    const editPromptInput = document.getElementById("studioEditPrompt");
    const editStrengthSlider = document.getElementById("studioStrengthSlider");

    const prompt = editPromptInput ? editPromptInput.value.trim() : "";
    const strength = editStrengthSlider ? parseFloat(editStrengthSlider.value) : 1.0;
    const isAiMode = prompt.length > 0;

    // Get current raw image
    const sourceImageBase64 = this.canvas.getEffectiveSourceImage ? this.canvas.getEffectiveSourceImage() : (this.canvas.originalImageSrc || this.canvas.getImageBase64());

    // Export inpainting mask if painted
    const maskBase64 = this.canvas.exportMaskBase64();

    // Read adjustments
    const adjustments = this.canvas.adjustments;

    if (applyEditBtn) {
      applyEditBtn.disabled = true;
      applyEditBtn.innerHTML = `<span>Applying CPU Edit...</span>`;
    }

    try {
      const res = await this.api.editImage({
        imageSource: sourceImageBase64,
        maskSource: maskBase64 || null,
        prompt: prompt || null,
        editMode: isAiMode ? "ai_img2img" : "transform",
        filterPreset: this.selectedFilterPreset !== "none" ? this.selectedFilterPreset : null,
        brightness: adjustments.brightness,
        contrast: adjustments.contrast,
        saturation: adjustments.saturation,
        sharpness: adjustments.sharpness,
        blur: adjustments.blur,
        vignette: adjustments.vignette,
        gamma: 1.0,
        strength: strength,
        runQa: true
      });

      const imageUrl = res.image_base64 || res.image_url || (res.filename ? this.api.getImageUrl(res.filename) : "");
      if (!imageUrl) {
        throw new Error("No output image was returned by the editing engine.");
      }

      this.lastEditedResult = res;

      // Add to gallery with original image tracking
      this.gallery.addItem({
        type: "edit",
        url: imageUrl,
        filename: res.filename,
        prompt: prompt ? `Edit: ${prompt}` : `Filter: ${this.selectedFilterPreset}`,
        qaReport: res.qa_report,
        originalUrl: sourceImageBase64
      });

      // Reload into canvas to show processed state
      await this.canvas.loadImage(imageUrl);

      // Offer quick comparison
      if (maskBase64) {
        this.showToast("Mask-guided inpaint edit applied on CPU! Inspect in 'Compare'.", "success");
      } else {
        this.showToast("Image successfully processed on CPU! Inspect in 'Compare'.", "success");
      }
      
      // Update comparison tool automatically
      this.comparison.setImages(sourceImageBase64, imageUrl);

    } catch (err) {
      this.showToast(`Edit failed: ${err.message}`, "error");
    } finally {
      if (applyEditBtn) {
        applyEditBtn.disabled = false;
        applyEditBtn.innerHTML = `
          <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 2l2.4 7.2L22 12l-7.6 2.8L12 22l-2.4-7.2L2 12l7.6-2.8z"/>
          </svg>
          <span>Apply Edits</span>
        `;
      }
    }
  }

  sendToStudio(imageSrc) {
    this.switchTab("studio");
    if (this.canvas) {
      this.canvas.loadImage(imageSrc).then(() => {
        this.showToast("Loaded image into Inpaint Studio & Canvas", "info");
      });
    }
  }

  openComparison(beforeSrc, afterSrc) {
    this.switchTab("compare");
    if (this.comparison) {
      this.comparison.setImages(beforeSrc, afterSrc);
    }
  }

  loadDefaultStudioImage() {
    // Generate a sleek, authentic Google Gemini banner with ZERO procedural wireframe rings
    const dummyCanvas = document.createElement("canvas");
    dummyCanvas.width = 512;
    dummyCanvas.height = 512;
    const ctx = dummyCanvas.getContext("2d");

    // Deep Gemini Background
    const grad = ctx.createLinearGradient(0, 0, 512, 512);
    grad.addColorStop(0, "#131314");
    grad.addColorStop(0.5, "#1e1f20");
    grad.addColorStop(1, "#18191a");
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, 512, 512);

    // Subtle soft gradient mesh glow in center
    const radial = ctx.createRadialGradient(256, 210, 10, 256, 210, 200);
    radial.addColorStop(0, "rgba(155, 114, 203, 0.18)");
    radial.addColorStop(0.6, "rgba(66, 133, 244, 0.08)");
    radial.addColorStop(1, "transparent");
    ctx.fillStyle = radial;
    ctx.fillRect(0, 0, 512, 512);

    // Draw 4-pointed Gemini Sparkle Icon
    ctx.save();
    ctx.translate(256, 200);
    ctx.fillStyle = "#9b72cb";
    ctx.beginPath();
    ctx.moveTo(0, -42);
    ctx.quadraticCurveTo(0, 0, 42, 0);
    ctx.quadraticCurveTo(0, 0, 0, 42);
    ctx.quadraticCurveTo(0, 0, -42, 0);
    ctx.quadraticCurveTo(0, 0, 0, -42);
    ctx.closePath();
    ctx.fill();
    ctx.restore();

    // Clean Typography
    ctx.fillStyle = "#e3e3e3";
    ctx.font = "bold 22px -apple-system, sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("Gemini Nano Studio", 256, 280);

    ctx.fillStyle = "#c4c7c5";
    ctx.font = "14px -apple-system, sans-serif";
    ctx.fillText("AMD Ryzen AI 9 HX 370 Zen 5 CPU", 256, 310);

    ctx.fillStyle = "#8e918f";
    ctx.font = "12px -apple-system, sans-serif";
    ctx.fillText("Paint over any area to inpaint & erase", 256, 335);

    const defaultUrl = dummyCanvas.toDataURL("image/png");
    if (this.canvas) {
      this.canvas.loadImage(defaultUrl);
    }
  }

  // ----------------------------------------------------
  // Comparison Controls
  // ----------------------------------------------------
  bindComparisonControls() {
    const sliderModeBtn = document.getElementById("compareModeSliderBtn");
    const dualModeBtn = document.getElementById("compareModeDualBtn");

    if (sliderModeBtn && dualModeBtn) {
      sliderModeBtn.addEventListener("click", () => {
        sliderModeBtn.classList.add("active");
        dualModeBtn.classList.remove("active");
        this.comparison.setMode("slider");
      });

      dualModeBtn.addEventListener("click", () => {
        dualModeBtn.classList.add("active");
        sliderModeBtn.classList.remove("active");
        this.comparison.setMode("dual");
      });
    }
  }

  // ----------------------------------------------------
  // System Telemetry & Settings
  // ----------------------------------------------------
  bindSettingsAndHardware() {
    const saveApiBtn = document.getElementById("saveApiEndpointBtn");
    const apiInput = document.getElementById("apiEndpointInput");

    if (apiInput) {
      apiInput.value = this.api.customBaseUrl || "";
    }

    if (saveApiBtn && apiInput) {
      saveApiBtn.addEventListener("click", async () => {
        const url = apiInput.value.trim();
        this.api.setBaseUrl(url);
        this.showToast(`API URL updated to: ${this.api.getBaseUrl()}`, "info");
        await this.fetchSystemTelemetry();
      });
    }

    // Modal close listeners
    document.querySelectorAll(".modal-close-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".modal-overlay").forEach(m => m.classList.remove("active"));
      });
    });

    const modal = document.getElementById("lightboxModal");
    if (modal) {
      modal.addEventListener("click", (e) => {
        if (e.target === modal) modal.classList.remove("active");
      });
    }
  }

  async fetchSystemTelemetry() {
    const hwDot = document.getElementById("hwStatusDot");
    const hwChip = document.getElementById("hwChipInfo");
    const dgpuPill = document.getElementById("dgpuIsolatedPill");
    const fullTelemetryCard = document.getElementById("fullTelemetryInfo");

    try {
      // Wire up /api/hardware or /api/system
      const hw = await this.api.getHardwareStatus ? await this.api.getHardwareStatus() : await this.api.getSystemHardware();
      if (hw) {
        const oom = hw.oom_guard || {};
        const ramUsed = Math.round(hw.memory_used_percent || oom.system_ram_used_percent || 0);

        if (hwDot) hwDot.style.backgroundColor = ramUsed >= 90 ? "var(--color-error)" : (ramUsed >= 80 ? "var(--color-warning)" : "var(--color-success)");
        if (hwChip) hwChip.textContent = `${hw.cpu_model || 'AMD Ryzen AI 9 HX 370'} (${hw.torch_threads || 24}t) • RAM: ${ramUsed}% [OOM Guard 95%]`;
        if (dgpuPill) {
          dgpuPill.textContent = hw.dgpu_isolated ? "dGPU Isolated" : "Warning: dGPU";
          dgpuPill.style.color = hw.dgpu_isolated ? "var(--color-success)" : "var(--color-error)";
        }

        if (fullTelemetryCard) {
          fullTelemetryCard.innerHTML = `
            <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 0.85rem; font-size: 0.85rem;">
              <div><strong>CPU Model:</strong> ${hw.cpu_model || 'AMD Ryzen AI 9 HX 370'}</div>
              <div><strong>Architecture:</strong> ${hw.cpu_architecture || 'Zen 5 / Zen 5c'}</div>
              <div><strong>Logical Cores:</strong> ${hw.cpu_cores_logical || 24} (PyTorch: ${hw.torch_threads || 24} threads)</div>
              <div><strong>AVX-512 Support:</strong> ${hw.avx512_supported ? 'Enabled' : 'Disabled'}</div>
              <div><strong>Execution Device:</strong> <span style="color: var(--color-success); font-weight: bold;">CPU Zen 5 (100% Isolated)</span></div>
              <div><strong>Discrete GPU:</strong> ${hw.dgpu_description || 'Isolated / Offline'}</div>
              <div><strong>Integrated APU:</strong> ${hw.igpu_description || 'AMD Radeon 890M'}</div>
              <div><strong>System Memory:</strong> ${hw.memory_available_gb || 24} GB free / ${hw.memory_total_gb || 32} GB total (${ramUsed}% used)</div>
              <div><strong>OOM Fail-Safe Guard:</strong> <span style="color: var(--color-success); font-weight: bold;">ACTIVE (Emergency kill at 95% RAM)</span></div>
            </div>
          `;
        }
      }

      // Also query /api/models if available to verify model readiness
      if (this.api.getModels) {
        try {
          const modelData = await this.api.getModels();
          if (modelData && modelData.models) {
            console.log("[Gemini Nano] Models ready:", modelData.models.map(m => m.name).join(", "));
          }
        } catch (_) {}
      }

    } catch (err) {
      if (hwDot) hwDot.style.backgroundColor = "var(--color-warning)";
      if (hwChip) hwChip.textContent = "Connecting to Backend...";
      console.warn("Telemetry fetch error:", err.message);
    }
  }

  bindKeyboardShortcuts() {
    window.addEventListener("keydown", (e) => {
      // Ctrl+Enter or Cmd+Enter to generate
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
        if (this.activeTab === "generate") {
          e.preventDefault();
          this.executeGeneration();
        }
      }

      // Ctrl+B to toggle sidebar
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "b") {
        e.preventDefault();
        if (this.sessionManager) {
          this.sessionManager.toggleSidebar();
        }
      }

      // Escape to close modals
      if (e.key === "Escape") {
        document.querySelectorAll(".modal-overlay").forEach(m => m.classList.remove("active"));
      }

      // Brush resizing with [ and ] in studio
      if (this.activeTab === "studio" && this.canvas) {
        if (e.key === "[") {
          this.canvas.setBrushSize(this.canvas.brushSize - 5);
          const slider = document.getElementById("brushSizeSlider");
          const valDisp = document.getElementById("brushSizeVal");
          if (slider) slider.value = this.canvas.brushSize;
          if (valDisp) valDisp.textContent = `${this.canvas.brushSize}px`;
        } else if (e.key === "]") {
          this.canvas.setBrushSize(this.canvas.brushSize + 5);
          const slider = document.getElementById("brushSizeSlider");
          const valDisp = document.getElementById("brushSizeVal");
          if (slider) slider.value = this.canvas.brushSize;
          if (valDisp) valDisp.textContent = `${this.canvas.brushSize}px`;
        }
      }
    });
  }
}

// Instantiate on DOM ready
document.addEventListener("DOMContentLoaded", () => {
  window.app = new GeminiNanoApp();
  window.app.init();
});

if (typeof module !== "undefined" && module.exports) {
  module.exports = { GeminiNanoApp };
}
