/**
 * Quality Assurance Critic Panel Renderer
 * Visualizes quality metrics, grades, and actionable suggestions from QA Agent
 */

class QAPanel {
  constructor(containerId = "qaPanelContainer") {
    this.container = typeof document !== 'undefined' ? document.getElementById(containerId) : null;
  }

  render(qaData) {
    if (!this.container) return;
    if (!qaData || typeof qaData !== 'object' || !qaData.quality_score) {
      this.container.innerHTML = "";
      this.container.style.display = "none";
      return;
    }

    this.container.style.display = "block";
    const score = Math.round(qaData.quality_score || 0);
    const grade = qaData.grade || "B";
    const status = qaData.status || "Acceptable";
    const metrics = qaData.metrics || {};
    const suggestions = qaData.suggestions || [];

    const gradeClass = grade.replace('+', '-plus');

    this.container.innerHTML = `
      <div class="qa-audit-card">
        <div class="qa-card-header">
          <div class="qa-card-title">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--gemini-purple)" stroke-width="2">
              <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>
            </svg>
            <span>AI Quality Critic Audit</span>
          </div>
          <div class="qa-grade-badge grade-${gradeClass}">
            Grade ${grade} &bull; ${score}/100 (${status})
          </div>
        </div>

        <div class="qa-metrics-grid">
          <div class="qa-metric-item">
            <span class="qa-metric-label">Sharpness</span>
            <span class="qa-metric-value" style="color: ${this.getMetricColor(metrics.sharpness || 0)}">
              ${metrics.sharpness || 0}%
            </span>
          </div>
          <div class="qa-metric-item">
            <span class="qa-metric-label">Contrast</span>
            <span class="qa-metric-value" style="color: ${this.getMetricColor(metrics.contrast || 0)}">
              ${metrics.contrast || 0}%
            </span>
          </div>
          <div class="qa-metric-item">
            <span class="qa-metric-label">Exposure</span>
            <span class="qa-metric-value" style="color: ${this.getMetricColor(metrics.exposure || 0)}">
              ${metrics.exposure || 0}%
            </span>
          </div>
          <div class="qa-metric-item">
            <span class="qa-metric-label">Vibrancy</span>
            <span class="qa-metric-value" style="color: ${this.getMetricColor(metrics.vibrancy || 0)}">
              ${metrics.vibrancy || 0}%
            </span>
          </div>
        </div>

        ${suggestions.length > 0 ? `
          <div class="qa-suggestions-list">
            <strong>Critique &amp; Tips:</strong> ${suggestions.join(" &bull; ")}
          </div>
        ` : ''}
      </div>
    `;
  }

  getMetricColor(val) {
    if (val >= 70) return "var(--color-success)";
    if (val >= 45) return "var(--color-warning)";
    return "var(--color-error)";
  }

  clear() {
    if (this.container) {
      this.container.innerHTML = "";
      this.container.style.display = "none";
    }
  }
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { QAPanel };
}
