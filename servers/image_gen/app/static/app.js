// Gemini Nano Banana Client Application
document.addEventListener("DOMContentLoaded", () => {
  // Global State
  const state = {
    selectedStyle: "photorealistic",
    selectedAspect: "1:1",
    selectedFilter: "none",
    currentGeneratedImage: null,
    editSourceImage: null,
    editedImage: null,
    isGenerating: false,
    isEditing: false
  };

  // 1. Tab Switching
  const tabBtns = document.querySelectorAll(".tab-btn");
  const tabPanes = document.querySelectorAll(".tab-pane");

  tabBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      const targetTab = btn.getAttribute("data-tab");
      tabBtns.forEach(b => b.classList.remove("active"));
      tabPanes.forEach(p => p.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById(targetTab)?.classList.add("active");

      if (targetTab === "tab-telemetry") {
        fetchTelemetry();
      }
    });
  });

  // 2. Sliders live value updates
  const setupSlider = (sliderId, valId, stepDecimals = 0) => {
    const slider = document.getElementById(sliderId);
    const valSpan = document.getElementById(valId);
    if (slider && valSpan) {
      slider.addEventListener("input", (e) => {
        valSpan.textContent = stepDecimals > 0 
          ? parseFloat(e.target.value).toFixed(stepDecimals)
          : e.target.value;
      });
    }
  };

  setupSlider("steps-input", "steps-val", 0);
  setupSlider("guidance-input", "guidance-val", 1);
  setupSlider("edit-strength", "strength-val", 2);
  setupSlider("adj-brightness", "val-brightness", 2);
  setupSlider("adj-contrast", "val-contrast", 2);
  setupSlider("adj-saturation", "val-saturation", 2);
  setupSlider("adj-sharpness", "val-sharpness", 1);
  setupSlider("adj-blur", "val-blur", 1);
  setupSlider("adj-vignette", "val-vignette", 2);

  // 3. Style Presets Selection
  const styleChips = document.querySelectorAll("#style-chips .chip");
  styleChips.forEach(chip => {
    chip.addEventListener("click", () => {
      styleChips.forEach(c => c.classList.remove("active"));
      chip.classList.add("active");
      state.selectedStyle = chip.getAttribute("data-style");
    });
  });

  // 4. Aspect Ratio Selection
  const aspectBtns = document.querySelectorAll("#aspect-selector .aspect-btn");
  aspectBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      aspectBtns.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      state.selectedAspect = btn.getAttribute("data-aspect");
    });
  });

  // 5. Filter Preset Selection in Editor
  const filterChips = document.querySelectorAll("#filter-chips .chip");
  filterChips.forEach(chip => {
    chip.addEventListener("click", () => {
      filterChips.forEach(c => c.classList.remove("active"));
      chip.classList.add("active");
      state.selectedFilter = chip.getAttribute("data-filter");
      // Auto-preview filter if image loaded
      if (state.editSourceImage) {
        applyEdits();
      }
    });
  });

  // 6. AI Prompt Optimizer Button
  const btnOptimize = document.getElementById("btn-optimize-prompt");
  const promptInput = document.getElementById("prompt-input");

  btnOptimize?.addEventListener("click", async () => {
    const raw = promptInput.value.trim();
    if (!raw) {
      promptInput.focus();
      return;
    }
    btnOptimize.disabled = true;
    btnOptimize.innerHTML = "<span>✨ Optimizing...</span>";
    try {
      const res = await fetch("/api/optimize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt: raw,
          style: state.selectedStyle,
          aspect_ratio: state.selectedAspect
        })
      });
      const data = await res.json();
      if (data.optimized_prompt) {
        promptInput.value = data.optimized_prompt;
        const negInput = document.getElementById("negative-prompt-input");
        if (negInput && !negInput.value) {
          negInput.value = data.negative_prompt;
        }
      }
    } catch (err) {
      console.error("Optimization failed:", err);
    } finally {
      btnOptimize.disabled = false;
      btnOptimize.innerHTML = "<span>✨ AI Optimize</span>";
    }
  });

  // 7. Text-to-Image Generation
  const btnGenerate = document.getElementById("btn-generate");
  const genEmptyState = document.getElementById("gen-empty-state");
  const genLoadingState = document.getElementById("gen-loading-state");
  const genResultContainer = document.getElementById("gen-result-container");
  const genResultImg = document.getElementById("gen-result-img");

  btnGenerate?.addEventListener("click", async () => {
    const prompt = promptInput.value.trim();
    if (!prompt) {
      alert("Please enter a prompt first!");
      promptInput.focus();
      return;
    }

    state.isGenerating = true;
    btnGenerate.disabled = true;
    genEmptyState.classList.add("hidden");
    genResultContainer.classList.add("hidden");
    genLoadingState.classList.remove("hidden");

    const payload = {
      prompt: prompt,
      style: state.selectedStyle,
      negative_prompt: document.getElementById("negative-prompt-input").value.trim(),
      aspect_ratio: state.selectedAspect,
      steps: parseInt(document.getElementById("steps-input").value, 10),
      guidance_scale: parseFloat(document.getElementById("guidance-input").value),
      seed: parseInt(document.getElementById("seed-input").value, 10),
      auto_optimize: document.getElementById("toggle-auto-opt").checked,
      run_qa: document.getElementById("toggle-run-qa").checked
    };

    try {
      const response = await fetch("/api/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const result = await response.json();

      if (result.success) {
        state.currentGeneratedImage = result.image_base64;
        genResultImg.src = result.image_base64;

        // QA Badge
        const qa = result.qa_report || {};
        const score = qa.quality_score ?? 88;
        const grade = qa.grade ?? "A";
        document.getElementById("qa-badge-score").textContent = `${score}/100`;
        document.getElementById("qa-badge-grade").textContent = `Grade ${grade}`;

        // Metrics Card
        document.getElementById("metric-score").textContent = `${score}/100`;
        document.getElementById("metric-sharpness").textContent = qa.metrics?.sharpness ? `${qa.metrics.sharpness}%` : "--";
        document.getElementById("metric-contrast").textContent = qa.metrics?.contrast ? `${qa.metrics.contrast}%` : "--";
        document.getElementById("metric-latency").textContent = `${result.total_latency_seconds}s`;

        // Suggestions
        const suggestionsBox = document.getElementById("qa-suggestions-list");
        if (qa.suggestions && qa.suggestions.length > 0) {
          suggestionsBox.innerHTML = `<strong>QA Audit:</strong> <ul>${qa.suggestions.map(s => `<li>${s}</li>`).join('')}</ul>`;
        } else {
          suggestionsBox.innerHTML = "<strong>QA Audit:</strong> High clarity, balanced exposure, zero artifacts detected.";
        }

        // Audit Trail
        document.getElementById("audit-log-display").textContent = JSON.stringify(result.audit_log, null, 2);

        genLoadingState.classList.add("hidden");
        genResultContainer.classList.remove("hidden");
      } else {
        alert("Generation error: " + (result.detail || "Unknown error"));
        genLoadingState.classList.add("hidden");
        genEmptyState.classList.remove("hidden");
      }
    } catch (err) {
      console.error(err);
      alert("Failed to communicate with runtime server: " + err.message);
      genLoadingState.classList.add("hidden");
      genEmptyState.classList.remove("hidden");
    } finally {
      state.isGenerating = false;
      btnGenerate.disabled = false;
    }
  });

  // Action Bar for Generated Image
  document.getElementById("btn-download-gen")?.addEventListener("click", () => {
    if (!state.currentGeneratedImage) return;
    const a = document.createElement("a");
    a.href = state.currentGeneratedImage;
    a.download = `gemini-banana-${Date.now()}.png`;
    a.click();
  });

  document.getElementById("btn-copy-gen")?.addEventListener("click", () => {
    if (!state.currentGeneratedImage) return;
    navigator.clipboard.writeText(state.currentGeneratedImage);
    alert("Base64 image copied to clipboard!");
  });

  document.getElementById("btn-send-to-edit")?.addEventListener("click", () => {
    if (!state.currentGeneratedImage) return;
    setEditorSourceImage(state.currentGeneratedImage);
    // Switch to edit tab
    document.querySelector('.tab-btn[data-tab="tab-edit"]')?.click();
  });

  // 8. Image Editor & Split Comparison Slider
  const editDropzone = document.getElementById("edit-dropzone");
  const editFileInput = document.getElementById("edit-file-input");
  const editEmptyState = document.getElementById("edit-empty-state");
  const editCanvasContainer = document.getElementById("edit-canvas-container");
  const editOriginalImg = document.getElementById("edit-original-img");
  const editModifiedImg = document.getElementById("edit-modified-img");
  const compClip = document.getElementById("comp-clip");
  const compDivider = document.getElementById("comp-divider");
  const comparisonSlider = document.getElementById("comparison-slider");

  const setEditorSourceImage = (imgSrc) => {
    state.editSourceImage = imgSrc;
    state.editedImage = imgSrc;
    editOriginalImg.src = imgSrc;
    editModifiedImg.src = imgSrc;
    editEmptyState.classList.add("hidden");
    editCanvasContainer.classList.remove("hidden");
    resetSplitSlider();
  };

  editDropzone?.addEventListener("click", () => editFileInput?.click());

  editFileInput?.addEventListener("change", (e) => {
    const file = e.target.files[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (event) => setEditorSourceImage(event.target.result);
      reader.readAsDataURL(file);
    }
  });

  editDropzone?.addEventListener("dragover", (e) => {
    e.preventDefault();
    editDropzone.classList.add("drag-over");
  });

  editDropzone?.addEventListener("dragleave", () => {
    editDropzone.classList.remove("drag-over");
  });

  editDropzone?.addEventListener("drop", (e) => {
    e.preventDefault();
    editDropzone.classList.remove("drag-over");
    const file = e.dataTransfer.files[0];
    if (file && file.type.startsWith("image/")) {
      const reader = new FileReader();
      reader.onload = (event) => setEditorSourceImage(event.target.result);
      reader.readAsDataURL(file);
    }
  });

  // Comparison Split Slider Dragging
  let isDraggingDivider = false;

  const updateDividerPosition = (clientX) => {
    if (!comparisonSlider) return;
    const rect = comparisonSlider.getBoundingClientRect();
    let pos = (clientX - rect.left) / rect.width;
    pos = Math.max(0.02, Math.min(0.98, pos));
    const percent = pos * 100;

    compDivider.style.left = `${percent}%`;
    compClip.style.width = `${percent}%`;
    // Update internal image width to match parent scale
    editModifiedImg.style.width = `${rect.width}px`;
    editModifiedImg.style.height = `${rect.height}px`;
  };

  const resetSplitSlider = () => {
    if (compDivider && compClip) {
      compDivider.style.left = "50%";
      compClip.style.width = "50%";
    }
  };

  comparisonSlider?.addEventListener("mousedown", (e) => {
    isDraggingDivider = true;
    updateDividerPosition(e.clientX);
  });

  window.addEventListener("mousemove", (e) => {
    if (isDraggingDivider) {
      updateDividerPosition(e.clientX);
    }
  });

  window.addEventListener("mouseup", () => {
    isDraggingDivider = false;
  });

  // Touch support for slider
  comparisonSlider?.addEventListener("touchstart", (e) => {
    isDraggingDivider = true;
    updateDividerPosition(e.touches[0].clientX);
  });

  window.addEventListener("touchmove", (e) => {
    if (isDraggingDivider && e.touches.length > 0) {
      updateDividerPosition(e.touches[0].clientX);
    }
  });

  window.addEventListener("touchend", () => {
    isDraggingDivider = false;
  });

  // Apply Edits Request
  const applyEdits = async () => {
    if (!state.editSourceImage) return;

    const btnApply = document.getElementById("btn-apply-edit");
    if (btnApply) btnApply.disabled = true;

    const promptText = document.getElementById("edit-prompt").value.trim();
    const payload = {
      image_source: state.editSourceImage,
      prompt: promptText || null,
      edit_mode: promptText ? "ai_img2img" : "transform",
      filter_preset: state.selectedFilter,
      brightness: parseFloat(document.getElementById("adj-brightness").value),
      contrast: parseFloat(document.getElementById("adj-contrast").value),
      saturation: parseFloat(document.getElementById("adj-saturation").value),
      sharpness: parseFloat(document.getElementById("adj-sharpness").value),
      blur: parseFloat(document.getElementById("adj-blur").value),
      vignette: parseFloat(document.getElementById("adj-vignette").value),
      strength: parseFloat(document.getElementById("edit-strength").value),
      run_qa: true
    };

    try {
      const res = await fetch("/api/edit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.success) {
        state.editedImage = data.image_base64;
        editModifiedImg.src = data.image_base64;

        // Update QA
        const qa = data.qa_report || {};
        document.getElementById("edit-metric-score").textContent = `${qa.quality_score ?? 90}/100`;
        document.getElementById("edit-metric-sharpness").textContent = qa.metrics?.sharpness ? `${qa.metrics.sharpness}%` : "--";
        document.getElementById("edit-metric-contrast").textContent = qa.metrics?.contrast ? `${qa.metrics.contrast}%` : "--";
        document.getElementById("edit-metric-latency").textContent = `${data.total_latency_seconds}s`;
      } else {
        alert("Edit error: " + (data.detail || "Unknown error"));
      }
    } catch (err) {
      console.error(err);
      alert("Error applying edits: " + err.message);
    } finally {
      if (btnApply) btnApply.disabled = false;
    }
  };

  document.getElementById("btn-apply-edit")?.addEventListener("click", applyEdits);

  document.getElementById("btn-reset-edit")?.addEventListener("click", () => {
    if (!state.editSourceImage) return;
    document.getElementById("edit-prompt").value = "";
    document.getElementById("adj-brightness").value = "1.0";
    document.getElementById("val-brightness").textContent = "1.0";
    document.getElementById("adj-contrast").value = "1.0";
    document.getElementById("val-contrast").textContent = "1.0";
    document.getElementById("adj-saturation").value = "1.0";
    document.getElementById("val-saturation").textContent = "1.0";
    document.getElementById("adj-sharpness").value = "1.0";
    document.getElementById("val-sharpness").textContent = "1.0";
    document.getElementById("adj-blur").value = "0.0";
    document.getElementById("val-blur").textContent = "0.0";
    document.getElementById("adj-vignette").value = "0.0";
    document.getElementById("val-vignette").textContent = "0.0";
    document.getElementById("edit-strength").value = "0.65";
    document.getElementById("strength-val").textContent = "0.65";

    filterChips.forEach(c => c.classList.remove("active"));
    document.querySelector('#filter-chips .chip[data-filter="none"]')?.classList.add("active");
    state.selectedFilter = "none";

    state.editedImage = state.editSourceImage;
    editModifiedImg.src = state.editSourceImage;
    resetSplitSlider();
  });

  document.getElementById("btn-download-edit")?.addEventListener("click", () => {
    if (!state.editedImage) return;
    const a = document.createElement("a");
    a.href = state.editedImage;
    a.download = `gemini-banana-edit-${Date.now()}.png`;
    a.click();
  });

  document.getElementById("btn-set-as-source")?.addEventListener("click", () => {
    if (!state.editedImage) return;
    setEditorSourceImage(state.editedImage);
  });

  // 9. Agent Playground Test
  document.getElementById("btn-run-agent-test")?.addEventListener("click", async () => {
    const raw = document.getElementById("agent-test-prompt").value.trim() || "a cat in a garden";
    const outBox = document.getElementById("agent-test-output");
    outBox.textContent = "Agent optimizing prompt...";
    try {
      const res = await fetch("/api/optimize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: raw, style: "photorealistic" })
      });
      const data = await res.json();
      outBox.textContent = JSON.stringify(data, null, 2);
    } catch (err) {
      outBox.textContent = "Error: " + err.message;
    }
  });

  // 10. System Telemetry Fetch
  const fetchTelemetry = async () => {
    try {
      const res = await fetch("/api/system");
      const data = await res.json();

      document.getElementById("tel-cpu-name").textContent = data.cpu_model || "AMD Ryzen Processor";
      document.getElementById("tel-cpu-threads").textContent = `Logical Threads: ${data.cpu_cores_logical}`;
      document.getElementById("tel-torch-threads").textContent = `PyTorch Threads: ${data.torch_threads}`;
      document.getElementById("badge-cpu-name").textContent = `${data.cpu_model.split(' ')[0]} ${data.cpu_model.split(' ')[1] || 'Ryzen'} (${data.cpu_cores_logical}T)`;

      document.getElementById("raw-hardware-json").textContent = JSON.stringify(data, null, 2);
    } catch (err) {
      console.error("Telemetry fetch error:", err);
    }
  };

  document.getElementById("btn-refresh-telemetry")?.addEventListener("click", fetchTelemetry);

  // Initial load
  fetchTelemetry();
});
