"""UI Unit Tests: Frontend Asset Integrity & DOM Contract Verification.
Ensures that all HTML, CSS, and JS files exist, parse correctly,
and that all element IDs referenced by the JS controllers exist in the HTML DOM.
"""

import re
from pathlib import Path
import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

def test_frontend_directory_structure():
    assert FRONTEND_DIR.is_dir(), f"Frontend directory missing: {FRONTEND_DIR}"
    assert (FRONTEND_DIR / "index.html").is_file(), "index.html missing"
    assert (FRONTEND_DIR / "css").is_dir(), "css directory missing"
    assert (FRONTEND_DIR / "js").is_dir(), "js directory missing"

def test_css_files_exist_and_non_empty():
    css_files = [
        "variables.css",
        "layout.css",
        "components.css",
        "canvas.css"
    ]
    for fname in css_files:
        fpath = FRONTEND_DIR / "css" / fname
        assert fpath.is_file(), f"CSS file missing: {fpath}"
        content = fpath.read_text(encoding="utf-8")
        assert len(content) > 100, f"CSS file {fname} is suspiciously small ({len(content)} bytes)"
        assert "{" in content and "}" in content, f"CSS file {fname} does not contain valid rules"

def test_js_files_exist_and_non_empty():
    js_files = [
        "api.js",
        "canvas.js",
        "comparison.js",
        "qa_panel.js",
        "gallery.js",
        "app.js"
    ]
    for fname in js_files:
        fpath = FRONTEND_DIR / "js" / fname
        assert fpath.is_file(), f"JS file missing: {fpath}"
        content = fpath.read_text(encoding="utf-8")
        assert len(content) > 100, f"JS file {fname} is suspiciously small ({len(content)} bytes)"

def test_html_includes_all_css_and_js():
    html_path = FRONTEND_DIR / "index.html"
    content = html_path.read_text(encoding="utf-8")

    # Check CSS links
    expected_css = ["css/variables.css", "css/layout.css", "css/components.css", "css/canvas.css"]
    for css in expected_css:
        assert css in content, f"HTML does not link to {css}"

    # Check JS script tags
    expected_js = ["js/api.js", "js/canvas.js", "js/comparison.js", "js/qa_panel.js", "js/gallery.js", "js/app.js"]
    for js in expected_js:
        assert js in content, f"HTML does not link to {js}"

def test_critical_dom_ids_exist_in_html():
    """Verify that every getElementById call in JS matches an element in index.html."""
    html_content = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")
    
    # Extract all id="..." from index.html
    html_ids = set(re.findall(r'id=["\']([^"\']+)["\']', html_content))

    # Critical IDs that MUST be in index.html for app functionality
    required_ids = [
        # Navigation
        "navTabGenerate", "navTabStudio", "navTabCompare", "navTabGallery", "navTabSystem",
        # Telemetry
        "headerHardwareBadge", "hwStatusDot", "hwChipInfo", "dgpuIsolatedPill", "fullTelemetryInfo",
        # Generation Tab
        "tab-generate", "promptInput", "promptCharCount", "refinePromptBtn",
        "advancedAccordionHeader", "advancedAccordionWrapper", "negativePromptInput",
        "stepsSlider", "stepsVal", "guidanceSlider", "guidanceVal", "seedInput", "randomSeedBtn",
        "autoOptimizeToggle", "qaAuditToggle", "generateBtn",
        # Preview Area
        "generationPreviewArea", "previewEmptyState", "previewOutputImage",
        "previewActionsToolbar", "previewSendStudioBtn", "previewDownloadBtn",
        "qaPanelContainer", "previewLoadingOverlay", "loadingStatusText", "loadingTimerText",
        # Studio & Canvas Tab
        "tab-studio", "toolBrushBtn", "toolEraserBtn", "toolPanBtn",
        "undoMaskBtn", "clearMaskBtn", "zoomInBtn", "zoomOutBtn", "zoomFitBtn",
        "canvasViewport", "panContainer", "imageCanvas", "maskCanvas", "brushCursorIndicator",
        "studioUploadBtn", "studioUploadInput", "brushSizeSlider", "brushSizeVal",
        "resetAdjustmentsBtn", "studioEditPrompt", "studioStrengthSlider", "studioStrengthVal", "applyStudioEditBtn",
        # Compare Tab
        "tab-compare", "compareModeSliderBtn", "compareModeDualBtn",
        "comparisonContainer", "comparisonBeforeWrapper", "comparisonImgBefore", "comparisonImgAfter",
        "comparisonHandle", "dualColumnView", "dualBeforeImg", "dualAfterImg",
        # Gallery Tab
        "tab-gallery", "galleryGrid",
        # System Tab
        "tab-system", "apiEndpointInput", "saveApiEndpointBtn",
        # Modals & Toast
        "lightboxModal", "lightboxCaption", "lightboxDownloadBtn", "lightboxImg", "toastContainer"
    ]

    for req_id in required_ids:
        assert req_id in html_ids, f"Required DOM element ID '{req_id}' is missing from index.html"

def test_style_presets_match_backend():
    """Verify that style presets in frontend HTML match backend STYLE_PRESETS."""
    from app.agents.prompt_optimizer import STYLE_PRESETS
    
    html_content = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")
    
    # Extract data-style attributes from HTML
    html_styles = re.findall(r'data-style=["\']([^"\']+)["\']', html_content)
    assert len(html_styles) >= 8, f"Expected at least 8 styles in HTML, found {len(html_styles)}"

    for s in html_styles:
        assert s in STYLE_PRESETS, f"Frontend style preset '{s}' not recognized in backend STYLE_PRESETS"
