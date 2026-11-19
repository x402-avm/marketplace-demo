/**
 * Google Gemini Nano - Persistent Dynamic Chat Session Manager
 * Handles creating, switching, renaming, deleting, and syncing chat sessions
 * with the FastAPI backend and maintaining active state across page reloads.
 */

class SessionManager {
  constructor(options = {}) {
    this.api = options.api || (typeof window !== "undefined" && window.api) || (typeof ApiClient !== "undefined" ? new ApiClient() : null);
    this.sessions = [];
    this.currentSessionId = null;
    this.storageKey = "gemini_nano_active_session_id";
    
    // DOM Containers
    this.container = options.container || this.getEl("sessionsList") || this.getEl("sessionListContainer");
    this.sidebar = options.sidebar || this.getEl("geminiSidebar");
  }

  getEl(id) {
    return typeof document !== "undefined" && document.getElementById ? document.getElementById(id) : null;
  }

  getCurrentSessionId() {
    return this.currentSessionId;
  }

  setCurrentSessionId(id) {
    this.currentSessionId = id;
    if (typeof localStorage !== "undefined") {
      if (id) {
        localStorage.setItem(this.storageKey, id);
      } else {
        localStorage.removeItem(this.storageKey);
      }
    }
  }

  async loadSessions() {
    try {
      if (!this.api) return [];
      const res = await this.api.getSessions();
      this.sessions = Array.isArray(res) ? res : (res && res.sessions ? res.sessions : []);

      // Check saved active session in localStorage
      let savedId = null;
      if (typeof localStorage !== "undefined") {
        savedId = localStorage.getItem(this.storageKey);
      }

      if (savedId && this.sessions.some(s => s.id === savedId)) {
        await this.selectSession(savedId);
      } else if (this.sessions.length > 0) {
        await this.selectSession(this.sessions[0].id);
      } else {
        await this.createSession("New Chat");
      }

      this.renderSessionsList();
      return this.sessions;
    } catch (err) {
      console.warn("[SessionManager] Failed to load sessions:", err.message);
      // Fallback: create a local session if offline
      if (!this.currentSessionId) {
        this.currentSessionId = `sess_${Date.now()}`;
      }
      return [];
    }
  }

  async createSession(title = null) {
    const defaultTitle = title || "New Chat";
    try {
      let newSession = null;
      if (this.api && typeof this.api.createSession === "function") {
        newSession = await this.api.createSession(defaultTitle);
      }
      
      if (!newSession || !newSession.id) {
        newSession = {
          id: `sess_${Date.now()}_${Math.random().toString(36).substring(2, 6)}`,
          title: defaultTitle,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          message_count: 0,
          messages: []
        };
      }

      // Add to front of session list
      this.sessions.unshift(newSession);
      this.setCurrentSessionId(newSession.id);

      // Reset workspace view to fresh greeting
      this.resetWorkspaceToHero();

      this.renderSessionsList();
      return newSession;
    } catch (err) {
      console.warn("[SessionManager] Create session error:", err.message);
      const fallback = {
        id: `sess_${Date.now()}`,
        title: defaultTitle,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        messages: []
      };
      this.sessions.unshift(fallback);
      this.setCurrentSessionId(fallback.id);
      this.resetWorkspaceToHero();
      this.renderSessionsList();
      return fallback;
    }
  }

  createNewSession(title = null) {
    return this.createSession(title);
  }

  async selectSession(sessionId) {
    if (!sessionId) return null;
    this.setCurrentSessionId(sessionId);
    this.renderSessionsList();

    try {
      if (!this.api || typeof this.api.getSession !== "function") return null;
      const session = await this.api.getSession(sessionId);
      if (session) {
        this.renderChatMessages(session.messages || []);
        
        // Update session in local array if needed
        const idx = this.sessions.findIndex(s => s.id === sessionId);
        if (idx !== -1) {
          this.sessions[idx] = { ...this.sessions[idx], ...session };
        }
        return session;
      }
    } catch (err) {
      console.warn(`[SessionManager] Could not load session ${sessionId}:`, err.message);
    }
    return null;
  }

  switchSession(sessionId) {
    return this.selectSession(sessionId);
  }

  async renameSession(sessionId, newTitle) {
    if (!sessionId || !newTitle || !newTitle.trim()) return;
    const cleanTitle = newTitle.trim();

    // Optimistic local update
    const sess = this.sessions.find(s => s.id === sessionId);
    if (sess) sess.title = cleanTitle;
    this.renderSessionsList();

    try {
      if (this.api && typeof this.api.renameSession === "function") {
        await this.api.renameSession(sessionId, cleanTitle);
      }
    } catch (err) {
      console.warn(`[SessionManager] Failed to rename session ${sessionId}:`, err.message);
    }
  }

  async deleteSession(sessionId) {
    if (!sessionId) return;
    if (typeof window !== "undefined" && window.confirm && !window.confirm("Delete this chat session and its history?")) {
      return;
    }

    const wasActive = this.currentSessionId === sessionId;
    this.sessions = this.sessions.filter(s => s.id !== sessionId);

    try {
      if (this.api && typeof this.api.deleteSession === "function") {
        await this.api.deleteSession(sessionId);
      }
    } catch (err) {
      console.warn(`[SessionManager] Failed to delete session ${sessionId}:`, err.message);
    }

    if (wasActive) {
      if (this.sessions.length > 0) {
        await this.selectSession(this.sessions[0].id);
      } else {
        await this.createSession("New Chat");
      }
    } else {
      this.renderSessionsList();
    }
  }

  resetWorkspaceToHero() {
    const emptyState = this.getEl("previewEmptyState");
    const activeCard = this.getEl("activeGenerationCard");
    const chatStream = this.getEl("geminiChatStream");
    const previewImg = this.getEl("previewOutputImage");

    if (emptyState) emptyState.style.display = "flex";
    if (activeCard) activeCard.style.display = "none";
    if (chatStream) chatStream.innerHTML = "";
    if (previewImg) {
      previewImg.src = "";
      previewImg.style.display = "none";
    }

    // Reset app active state
    if (typeof window !== "undefined" && window.app) {
      window.app.lastGeneratedResult = null;
      window.app.lastEditedResult = null;
      if (typeof window.app.clearEditReference === "function") {
        window.app.clearEditReference();
      }
    }
  }

  renderChatMessages(messages = []) {
    const emptyState = this.getEl("previewEmptyState");
    const activeCard = this.getEl("activeGenerationCard");
    const chatStream = this.getEl("geminiChatStream");
    const previewImg = this.getEl("previewOutputImage");

    if (!messages || messages.length === 0) {
      this.resetWorkspaceToHero();
      return;
    }

    if (emptyState) emptyState.style.display = "none";
    if (chatStream) chatStream.innerHTML = "";

    let lastImageSrc = null;
    let lastFilename = null;
    let lastQaReport = null;

    messages.forEach(msg => {
      if (msg.role === "user") {
        const bubble = document.createElement("div");
        bubble.className = "user-prompt-bubble";
        bubble.innerHTML = `
          <div class="user-avatar-icon">U</div>
          <div class="user-prompt-content">
            <div class="user-prompt-text">${this.escapeHtml(msg.content || "")}</div>
            ${msg.metadata && msg.metadata.style ? `
              <div class="user-prompt-badges">
                <span class="user-badge-chip">🎨 ${this.escapeHtml(msg.metadata.style)}</span>
                ${msg.metadata.aspect_ratio ? `<span class="user-badge-chip">📐 ${this.escapeHtml(msg.metadata.aspect_ratio)}</span>` : ""}
              </div>
            ` : ""}
          </div>
        `;
        chatStream.appendChild(bubble);
      } else if (msg.role === "assistant" && (msg.image_url || msg.image_path)) {
        const imgUrl = msg.image_url || (msg.image_path ? `/api/image/${msg.image_path.split('/').pop()}` : "");
        lastImageSrc = imgUrl;
        lastFilename = msg.image_path ? msg.image_path.split('/').pop() : "gemini_image.png";
        if (msg.metadata && msg.metadata.qa_report) {
          lastQaReport = msg.metadata.qa_report;
        }

        const card = document.createElement("div");
        card.className = "gemini-generation-card";
        const latency = (msg.metadata && msg.metadata.latency_seconds) ? `${msg.metadata.latency_seconds}s` : "1.2s";
        
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
              <span>✨ Qwen 2.1 Heretic NVFP4 • AMD Ryzen AI 9 HX 370 • ${latency}</span>
            </div>
          </div>
          <div class="image-display-frame">
            <img src="${imgUrl}" alt="Session Image" style="max-width: 100%; max-height: 58vh; object-fit: contain; display: block;">
          </div>
          <div class="gemini-action-chips">
            <button type="button" class="gemini-chip-btn chip-primary" onclick="window.app && window.app.setEditReference('${imgUrl}', '${lastFilename}')">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 2L14.8 8.6L22 12L14.8 15.4L12 22L9.2 15.4L2 12L9.2 8.6L12 2Z"/>
              </svg>
              <span>Edit with Prompt</span>
            </button>
            <button type="button" class="gemini-chip-btn" onclick="window.app && window.app.sendToStudio('${imgUrl}')">
              <span>🖌️ Inpaint &amp; Erase</span>
            </button>
            <button type="button" class="gemini-chip-btn" onclick="window.gallery && window.gallery.download('${imgUrl}', '${lastFilename}')">
              <span>⬇️ Download</span>
            </button>
          </div>
        `;
        chatStream.appendChild(card);
      }
    });

    // Update bottom active generation card with latest image
    if (lastImageSrc && previewImg && activeCard) {
      previewImg.src = lastImageSrc;
      previewImg.style.display = "block";
      activeCard.style.display = "flex";

      if (typeof window !== "undefined" && window.app) {
        window.app.lastGeneratedResult = {
          image_base64: lastImageSrc,
          filename: lastFilename,
          qa_report: lastQaReport
        };
      }
    }

    // Scroll to latest message
    const feed = this.getEl("generationPreviewArea");
    if (feed) feed.scrollTop = feed.scrollHeight;
  }

  renderSessionsList() {
    const listContainer = this.container || this.getEl("sessionsList") || this.getEl("sessionListContainer");
    if (!listContainer) return;

    listContainer.innerHTML = "";

    if (this.sessions.length === 0) {
      listContainer.innerHTML = `
        <div style="padding: 1.25rem 1rem; text-align: center; color: var(--text-muted); font-size: 0.8rem;">
          No previous chats yet.<br>Click <strong>+ New Chat</strong> to begin!
        </div>
      `;
      return;
    }

    this.sessions.forEach(sess => {
      const isActive = sess.id === this.currentSessionId;
      const item = document.createElement("div");
      item.className = `session-list-item ${isActive ? "active" : ""}`;
      item.setAttribute("data-session-id", sess.id);

      const title = this.escapeHtml(sess.title || "New Chat");
      const timeStr = this.formatRelativeTime(sess.updated_at || sess.created_at);

      item.innerHTML = `
        <div class="session-item-main" title="${title}">
          <div class="session-sparkle-icon">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 2L14.8 8.6L22 12L14.8 15.4L12 22L9.2 15.4L2 12L9.2 8.6L12 2Z"/>
            </svg>
          </div>
          <div class="session-text-wrap">
            <span class="session-title">${title}</span>
            <span class="session-time">${timeStr}</span>
          </div>
        </div>
        <div class="session-item-actions">
          <button type="button" class="session-action-btn btn-rename-session" title="Rename Chat">✏️</button>
          <button type="button" class="session-action-btn btn-delete-session" title="Delete Chat">🗑️</button>
        </div>
      `;

      // Select session on click
      item.querySelector(".session-item-main").addEventListener("click", () => {
        if (this.currentSessionId !== sess.id) {
          this.selectSession(sess.id);
        }
      });

      // Rename session
      item.querySelector(".btn-rename-session").addEventListener("click", (e) => {
        e.stopPropagation();
        const newTitle = prompt("Enter new title for this chat session:", sess.title);
        if (newTitle && newTitle.trim()) {
          this.renameSession(sess.id, newTitle.trim());
        }
      });

      // Delete session
      item.querySelector(".btn-delete-session").addEventListener("click", (e) => {
        e.stopPropagation();
        this.deleteSession(sess.id);
      });

      listContainer.appendChild(item);
    });
  }

  toggleSidebar() {
    const sidebar = this.sidebar || this.getEl("geminiSidebar");
    if (sidebar) {
      sidebar.classList.toggle("collapsed");
      const isCollapsed = sidebar.classList.contains("collapsed");
      if (typeof localStorage !== "undefined") {
        localStorage.setItem("gemini_sidebar_collapsed", isCollapsed ? "1" : "0");
      }
    }
  }

  formatRelativeTime(isoString) {
    if (!isoString) return "";
    try {
      const date = new Date(isoString);
      const diffSec = Math.floor((Date.now() - date.getTime()) / 1000);
      if (diffSec < 60) return "Just now";
      if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
      if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
      return `${Math.floor(diffSec / 86400)}d ago`;
    } catch (_) {
      return "";
    }
  }

  escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }
}

// Export singleton instance or class
if (typeof module !== "undefined" && module.exports) {
  module.exports = { SessionManager };
}
