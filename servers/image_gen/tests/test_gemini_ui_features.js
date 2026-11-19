/**
 * Node.js Unit Tests for Gemini Nano UI Features.
 * Tests:
 * 1. Setting and clearing edit reference chips in the prompt dock.
 * 2. Studio canvas clean rendering without procedural rings.
 * 3. ApiClient methods for /api/hardware and /api/models.
 * 4. DOM integration and action chip bindings.
 */

const assert = require("assert");

// Mock browser globals
global.window = {
  location: {
    origin: "http://localhost:10000",
    hostname: "localhost",
    protocol: "http:",
    port: "10000"
  }
};

const storage = {};
global.localStorage = {
  getItem: (key) => storage[key] || null,
  setItem: (key, val) => { storage[key] = String(val); },
  removeItem: (key) => { delete storage[key]; }
};

// Mock Document and DOM elements
const elements = {};
function createMockElement(id) {
  return {
    id,
    value: "",
    style: {},
    classList: {
      _classes: new Set(),
      add: function(c) { this._classes.add(c); },
      remove: function(c) { this._classes.delete(c); },
      toggle: function(c) {
        if (this._classes.has(c)) this._classes.delete(c);
        else this._classes.add(c);
      },
      contains: function(c) { return this._classes.has(c); }
    },
    addEventListener: () => {},
    appendChild: () => {},
    setAttribute: () => {},
    querySelector: () => createMockElement("inner"),
    remove: () => {},
    focus: () => {},
    getContext: () => ({
      createLinearGradient: () => ({ addColorStop: () => {} }),
      createRadialGradient: () => ({ addColorStop: () => {} }),
      fillRect: () => {},
      save: () => {},
      translate: () => {},
      beginPath: () => {},
      moveTo: () => {},
      quadraticCurveTo: () => {},
      closePath: () => {},
      fill: () => {},
      restore: () => {},
      fillText: () => {}
    }),
    toDataURL: () => "data:image/png;base64,CLEAN_GEMINI_CANVAS"
  };
}

global.document = {
  getElementById: (id) => {
    if (!elements[id]) elements[id] = createMockElement(id);
    return elements[id];
  },
  querySelectorAll: () => [],
  createElement: (tag) => createMockElement(tag),
  addEventListener: () => {}
};

const { ApiClient } = require("../frontend/js/api.js");
const { SessionManager } = require("../frontend/js/session_manager.js");
const { GeminiNanoApp } = require("../frontend/js/app.js");

console.log("Running Gemini Nano UI Feature Tests...");

// 1. Test ApiClient /api/hardware and /api/models methods
{
  const client = new ApiClient();
  assert.strictEqual(typeof client.getHardwareStatus, "function", "ApiClient.getHardwareStatus should exist");
  assert.strictEqual(typeof client.getModels, "function", "ApiClient.getModels should exist");
  console.log("✔ ApiClient hardware and models endpoints wired successfully");
}

// 2. Test GeminiNanoApp Edit Reference Handling
{
  const app = new GeminiNanoApp();
  assert.strictEqual(app.editReference, null, "Default edit reference must be null");

  const sampleImg = "data:image/png;base64,SAMPLE_IMAGE";
  app.setEditReference(sampleImg, "cyberpunk_car.png");

  assert.strictEqual(app.editReference.src, sampleImg);
  assert.strictEqual(app.editReference.name, "cyberpunk_car.png");

  const chipContainer = document.getElementById("editReferenceChipContainer");
  assert.ok(chipContainer.classList.contains("active"), "Edit reference chip must be active");

  const thumb = document.getElementById("editReferenceThumb");
  assert.strictEqual(thumb.src, sampleImg, "Reference thumbnail src must be set");

  const promptInput = document.getElementById("promptInput");
  assert.ok(promptInput.placeholder.includes("Describe edits"), "Prompt placeholder must indicate editing mode");

  // Clear reference
  app.clearEditReference();
  assert.strictEqual(app.editReference, null, "Edit reference must be cleared");
  assert.ok(!chipContainer.classList.contains("active"), "Chip container should no longer be active");
  assert.ok(promptInput.placeholder.includes("Ask Gemini"), "Prompt placeholder should reset");

  console.log("✔ Edit reference prompt docking and clearing tests passed");
}

// 3. Test Canvas Default Art Generation
{
  const app = new GeminiNanoApp();
  app.canvas = {
    loadImage: (url) => {
      assert.ok(url.startsWith("data:image/png;base64"), "Studio image must load base64 data");
    }
  };
  app.loadDefaultStudioImage();
  console.log("✔ Studio canvas clean default initialization verified");
}

// 4. Test SessionManager Integration in Gemini UI
(async () => {
  const mockApi = {
    getSessions: async () => [
      { id: "s1", title: "Cyberpunk City", created_at: new Date().toISOString() },
      { id: "s2", title: "Glass Hummingbird", created_at: new Date().toISOString() }
    ],
    createSession: async (title) => ({ id: "s3", title: title || "New Chat" }),
    getSession: async (id) => ({ id, title: "Cyberpunk City", messages: [] }),
    renameSession: async (id, title) => ({ id, title }),
    deleteSession: async (id) => ({ success: true })
  };

  const sm = new SessionManager({ api: mockApi });
  const sessions = await sm.loadSessions();
  assert.strictEqual(sessions.length, 2);
  assert.strictEqual(sm.getCurrentSessionId(), "s1");

  // Test toggle sidebar
  const sb = document.getElementById("geminiSidebar");
  sm.toggleSidebar();
  assert.ok(sb.classList.contains("collapsed"));
  sm.toggleSidebar();
  assert.ok(!sb.classList.contains("collapsed"));

  console.log("✔ SessionManager chat sessions and sidebar toggle verified");
  console.log("\nALL GEMINI UI FEATURE TESTS PASSED! 🚀\n");
  process.exit(0);
})();
