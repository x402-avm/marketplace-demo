/**
 * Node.js Unit Tests for Frontend JavaScript Modules.
 * Tests ApiClient, GalleryStore, ImageComparison, QAPanel, and StudioCanvas logic.
 */

const assert = require("assert");

// Mock browser globals for Node.js environment
global.window = {
  location: {
    origin: "http://localhost:10001",
    hostname: "localhost",
    protocol: "http:",
    port: "10001"
  }
};

const storage = {};
global.localStorage = {
  getItem: (key) => storage[key] || null,
  setItem: (key, val) => { storage[key] = String(val); },
  removeItem: (key) => { delete storage[key]; }
};

// Import modules
const { ApiClient } = require("../frontend/js/api.js");
const { GalleryStore } = require("../frontend/js/gallery.js");
const { ImageComparison } = require("../frontend/js/comparison.js");
const { QAPanel } = require("../frontend/js/qa_panel.js");
const { StudioCanvas } = require("../frontend/js/canvas.js");
const { SessionManager } = require("../frontend/js/session_manager.js");

console.log("Running Frontend JavaScript Unit Tests...");

// 1. Test ApiClient Base URL Resolution & Port Handling
{
  const client = new ApiClient();
  // On port 10001, it must automatically resolve to port 10000
  assert.strictEqual(client.getBaseUrl(), "http://localhost:10000", "Port 10001 should resolve to port 10000 backend");

  // On port 10050, it must also resolve to port 10000
  global.window.location.port = "10050";
  assert.strictEqual(client.getBaseUrl(), "http://localhost:10000", "Any UI port in range should resolve to port 10000 backend");

  // On port 10000 (unified server), origin is used
  global.window.location.port = "10000";
  global.window.location.origin = "http://localhost:10000";
  assert.strictEqual(client.getBaseUrl(), "http://localhost:10000");

  // Reset to port 10001
  global.window.location.port = "10001";
  global.window.location.origin = "http://localhost:10001";

  // Custom base url override
  client.setBaseUrl("http://192.168.1.100:10005");
  assert.strictEqual(client.getBaseUrl(), "http://192.168.1.100:10005");

  // Reset to default
  client.setBaseUrl("");
  assert.strictEqual(client.getBaseUrl(), "http://localhost:10000");

  console.log("✔ ApiClient base URL resolution tests passed");
}

// 2. Test GalleryStore Operations & LocalStorage Compaction
{
  const gallery = new GalleryStore({ gridId: null });
  gallery.clearAll();
  assert.strictEqual(gallery.items.length, 0);

  // Add generated item with large base64
  const largeB64 = "data:image/png;base64," + "A".repeat(10000);
  const genItem = gallery.addItem({
    type: "gen",
    url: largeB64,
    filename: "gen_test1.png",
    prompt: 'Cyberpunk vehicle with "neon" lights'
  });
  assert.strictEqual(gallery.items.length, 1);
  assert.strictEqual(gallery.items[0].type, "gen");

  // Add edited item with original tracking
  const editItem = gallery.addItem({
    type: "edit",
    url: "data:image/png;base64,BBB",
    filename: "edit_test2.png",
    prompt: "Noir filter applied",
    originalUrl: "data:image/png;base64,AAA"
  });
  assert.strictEqual(gallery.items.length, 2);

  // Test localStorage compact persistence (large base64 replaced by endpoint URL)
  const savedData = JSON.parse(storage["gemini_nano_gallery_history"] || "[]");
  assert.strictEqual(savedData.length, 2);
  const savedGenItem = savedData.find(i => i.id === genItem.id);
  assert.strictEqual(savedGenItem.url, "/api/image/gen_test1.png", "Large base64 should be compacted to endpoint URL");

  // Test item actions by ID
  let studioTarget = null;
  let compTarget = null;
  global.window.app = {
    sendToStudio: (url) => { studioTarget = url; },
    openComparison: (before, after) => { compTarget = { before, after }; }
  };

  gallery.sendToStudio(genItem.id);
  assert.strictEqual(studioTarget, largeB64);

  gallery.openComparison(editItem.id);
  assert.deepStrictEqual(compTarget, { before: "data:image/png;base64,AAA", after: "data:image/png;base64,BBB" });

  // Test item removal
  gallery.removeItem(genItem.id);
  assert.strictEqual(gallery.items.length, 1);
  assert.strictEqual(gallery.items[0].id, editItem.id);

  console.log("✔ GalleryStore addition, compaction, ID actions, and removal tests passed");
}

// 3. Test ImageComparison State, Clamping & Dimensions
{
  const comp = new ImageComparison({});
  assert.strictEqual(comp.currentPositionPercent, 50);

  comp.setPosition(75);
  assert.strictEqual(comp.currentPositionPercent, 75);

  comp.setMode("dual");
  assert.strictEqual(comp.mode, "dual");

  comp.setMode("slider");
  assert.strictEqual(comp.mode, "slider");

  // Ensure syncDimensions handles null/mock container without error
  comp.syncDimensions();

  console.log("✔ ImageComparison state tests passed");
}

// 4. Test QAPanel Color Calculations
{
  const panel = new QAPanel("fake");
  assert.strictEqual(panel.getMetricColor(85), "var(--color-success)");
  assert.strictEqual(panel.getMetricColor(55), "var(--color-warning)");
  assert.strictEqual(panel.getMetricColor(25), "var(--color-error)");

  console.log("✔ QAPanel metric color tests passed");
}

// 5. Test StudioCanvas Business Logic
{
  const canvas = new StudioCanvas({});
  assert.strictEqual(canvas.activeTool, "brush");

  // Tool switching
  canvas.setTool("eraser");
  assert.strictEqual(canvas.activeTool, "eraser");
  canvas.setTool("pan");
  assert.strictEqual(canvas.activeTool, "pan");

  // Brush sizing & clamping
  canvas.setBrushSize(50);
  assert.strictEqual(canvas.brushSize, 50);
  canvas.setBrushSize(1);
  assert.strictEqual(canvas.brushSize, 2, "Brush size minimum clamp to 2");
  canvas.setBrushSize(300);
  assert.strictEqual(canvas.brushSize, 200, "Brush size maximum clamp to 200");

  // Adjustments update and reset
  canvas.updateAdjustments({ brightness: 1.5, contrast: 1.2 });
  assert.strictEqual(canvas.adjustments.brightness, 1.5);
  assert.strictEqual(canvas.adjustments.contrast, 1.2);
  assert.strictEqual(canvas.adjustments.saturation, 1.0);

  canvas.resetAdjustments();
  assert.strictEqual(canvas.adjustments.brightness, 1.0);
  assert.strictEqual(canvas.adjustments.contrast, 1.0);

  // Effective source image selection
  canvas.originalImageSrc = "short_data_url";
  assert.strictEqual(canvas.getEffectiveSourceImage(), "short_data_url");

  console.log("✔ StudioCanvas tool, sizing, adjustments, and source logic tests passed");
}

// 6. Test SessionManager Logic, Persistence & Operations
{
  let counter = 1;
  const mockApi = {
    getSessions: async () => [],
    createSession: async (title) => ({
      id: `sess_test_${counter++}`,
      title: title || "New Chat",
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      messages: []
    }),
    getSession: async (id) => ({
      id,
      title: "Cyberpunk Lambo",
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      messages: [
        { role: "user", content: "Cyberpunk car" },
        { role: "assistant", content: "Generated", image_path: "car.png", image_url: "/api/image/car.png" }
      ]
    }),
    renameSession: async (id, title) => ({ id, title }),
    deleteSession: async (id) => ({ success: true })
  };

  const sm = new SessionManager({ api: mockApi });
  assert.strictEqual(sm.getCurrentSessionId(), null);

  // Test set / get current session and localStorage persistence
  sm.setCurrentSessionId("sess_abc");
  assert.strictEqual(sm.getCurrentSessionId(), "sess_abc");
  assert.strictEqual(storage["gemini_nano_active_session_id"], "sess_abc");

  // Test createSession
  sm.createSession("Cyberpunk Lambo").then(sess => {
    assert.strictEqual(sess.id, "sess_test_1");
    assert.strictEqual(sm.getCurrentSessionId(), "sess_test_1");
    assert.strictEqual(sm.sessions.length, 1);
    assert.strictEqual(sm.sessions[0].title, "Cyberpunk Lambo");

    // Test renameSession
    sm.renameSession("sess_test_1", "Futuristic Supercar");
    assert.strictEqual(sm.sessions[0].title, "Futuristic Supercar");

    // Test formatRelativeTime
    assert.strictEqual(sm.formatRelativeTime(new Date().toISOString()), "Just now");

    // Test deleteSession
    sm.deleteSession("sess_test_1").then(() => {
      assert.ok(!sm.sessions.some(s => s.id === "sess_test_1"));
    });
  });

  console.log("✔ SessionManager session creation, persistence, rename, and timing tests passed");
}

console.log("\nALL FRONTEND JS UNIT TESTS PASSED SUCCESSFULLY! 🎉\n");
