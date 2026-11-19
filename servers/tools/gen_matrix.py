"""Source of truth for tools/test_matrix.json (run: python3 tools/gen_matrix.py)."""
import json
from pathlib import Path

def P(ext):  # regex capturing a file path with this extension
    return r"([\w./+-]+\." + ext + r")\b"

RESUME_A = ("Probe Person\nSenior Python Engineer\nExperience: Built Python FastAPI services and Docker deployments at Acme. "
            "Responsible for payment APIs. Increased throughput by 40%. Skills: Python, FastAPI, Docker, SQL, Algorand.")
RESUME_B = "Jo Doe\nCashier\nResponsible for register."
JD = "Acme Corp is hiring a Backend Engineer. Requirements: Python, FastAPI, Kubernetes, PostgreSQL."
FAKE = [r"example\.com", r"The quick brown fox", r"Chapter 1: Introduction to OCR"]

M = {
 "tts": {"tools": ["synthesize_speech"], "cases": [
   {"id": "speak", "tool": "synthesize_speech", "args": {"text": "Hello from the probe.", "voice": "af_heart"},
    "expect": ["(?i)success"], "artifacts": [{"regex": P("wav"), "min_size": 10000}], "unique_across_ports": True, "timeout": 180},
   {"id": "too_long", "tool": "synthesize_speech", "args": {"text": "a" * 1200}, "expect": ["1000 character"], "must_error": True}]},
 "web_mcp": {"tools": ["web_open_page", "web_screen_shoot", "web_page_info", "web_click_button", "send_api_request", "ddg_search"], "cases": [
   {"id": "open", "tool": "web_open_page", "args": {"url": "https://example.com"}, "expect": ["Opened https://example.com"], "timeout": 60},
   {"id": "info", "tool": "web_page_info", "args": {}, "expect": ["Example Domain"]},
   {"id": "shot", "tool": "web_screen_shoot", "args": {"filename": "{TMP}/shot_{PORT}.png"}, "artifacts": [{"regex": P("png"), "min_size": 2000}]},
   {"id": "click", "tool": "web_click_button", "args": {"selector": "a"}, "expect": ["Successfully clicked"], "timeout": 60},
   {"id": "info_url", "tool": "web_page_info", "args": {"url": "https://example.com"}, "expect": ["Example Domain"], "timeout": 60},
   {"id": "shot_url", "tool": "web_screen_shoot", "args": {"url": "https://example.com", "filename": "probe_shot.png"}, "expect": ["Screenshot saved"], "artifacts": [{"regex": P("png"), "min_size": 2000}], "timeout": 60},
   {"id": "click_url", "tool": "web_click_button", "args": {"url": "https://example.com", "selector": "a"}, "expect": ["Successfully clicked"], "timeout": 60},
   {"id": "api", "tool": "send_api_request", "args": {"url": "https://example.com", "method": "GET"}, "expect": ['"status_code": 200']},
   {"id": "search", "tool": "ddg_search", "args": {"query": "Model Context Protocol", "max_results": 2}, "expect": ['"results"', "https?://"], "timeout": 60},
   {"id": "neg_api", "tool": "send_api_request", "args": {"url": "http://127.0.0.1:4002/v1/wallets", "method": "GET"}, "expect": ["blocked private address"], "must_error": True},
   {"id": "neg_open", "tool": "web_open_page", "args": {"url": "http://localhost:4001/v2/status"}, "expect": ["blocked private address"], "must_error": True},
   {"id": "neg_shot_path", "tool": "web_screen_shoot", "args": {"filename": "/tmp/x.png"}, "expect": ["path not allowed"], "must_error": True}]},
 "invoice_mcp": {"tools": ["generate_invoice"], "cases": [
   {"id": "invoice", "tool": "generate_invoice", "args": {"customer_name": "Probe Co", "items": [{"name": "Widget", "amount": 10.5, "quantity": 2}, {"name": "Setup", "amount": 5.0, "quantity": 1}]},
    "artifacts": [{"regex": P("pdf"), "pdf_text": ["Probe Co", "Widget", "26.00"]}]}]},
 "domain_mcp": {"tools": ["domain_whois", "domain_dns", "domain_ssl", "domain_ip"], "cases": [
   {"id": "whois", "tool": "domain_whois", "args": {"domain": "github.com"}, "expect": ["(?i)github"], "reject": ['"detail"'], "timeout": 60},
   {"id": "dns", "tool": "domain_dns", "args": {"domain": "github.com"}, "expect": ['"A"', r"\d+\.\d+\.\d+\.\d+"]},
   {"id": "ssl", "tool": "domain_ssl", "args": {"domain": "github.com"}, "expect": [r"\d{4} GMT"]},
   {"id": "ip", "tool": "domain_ip", "args": {"domain": "github.com"}, "expect": [r"\d+\.\d+\.\d+\.\d+"]},
   {"id": "bad_domain", "tool": "domain_ip", "args": {"domain": "no-such-host-xyz.invalid"}, "expect": ["(?i)error|not known|failed|detail"], "must_error": True}]},
 "yt_mcp": {"tools": ["download_yt_video", "get_yt_transcript"], "cases": [
   {"id": "transcript", "tool": "get_yt_transcript", "args": {"video_id": "jNQXAC9IVRw"}, "expect": ["success", "(?i)elephant"], "timeout": 90},
   {"id": "download", "tool": "download_yt_video", "args": {"url": "https://www.youtube.com/watch?v=jNQXAC9IVRw", "format": "audio"},
    "expect": ["yt_mcp/outputs"], "artifacts": [{"regex": r"'file': '([^']+)'", "min_size": 20000}], "timeout": 300}]},
 "sandbox_mcp": {"tools": ["run_sandbox_code"], "cases": [
   {"id": "python", "tool": "run_sandbox_code", "args": {"language": "python", "code": "print(sum(range(10)))"}, "expect": [r"Stdout:\n45"]},
   {"id": "javascript", "tool": "run_sandbox_code", "args": {"language": "javascript", "code": "console.log(6*7)"}, "expect": [r"Stdout:\n42"]},
   {"id": "c", "tool": "run_sandbox_code", "args": {"language": "c", "code": "#include <stdio.h>\nint main(){printf(\"c-ok %d\\n\", 3*3);return 0;}"}, "expect": ["c-ok 9"], "timeout": 60},
   {"id": "cpp", "tool": "run_sandbox_code", "args": {"language": "cpp", "code": "#include <iostream>\nint main(){std::cout<<\"cpp-ok \"<<4*4<<std::endl;}"}, "expect": ["cpp-ok 16"], "timeout": 60},
   {"id": "java", "tool": "run_sandbox_code", "args": {"language": "java", "code": "public class Main{public static void main(String[] a){System.out.println(\"java-ok \"+5*5);}}"}, "expect": ["java-ok 25"], "timeout": 60},
   {"id": "timeout", "tool": "run_sandbox_code", "args": {"language": "python", "code": "while True: pass"}, "expect": ["(?i)timed out"], "timeout": 60},
   {"id": "unsupported", "tool": "run_sandbox_code", "args": {"language": "cobol", "code": "x"}, "expect": ["(?i)unsupported"], "must_error": True}]},
 "latex_mcp": {"tools": ["compile_latex_to_pdf"], "cases": [
   {"id": "compile", "tool": "compile_latex_to_pdf", "args": {"latex_string": "\\documentclass{article}\\begin{document}Probe LaTeX 42\\end{document}"},
    "expect": ["latex_mcp/outputs"], "artifacts": [{"regex": P("pdf"), "pdf_text": ["Probe LaTeX 42"]}], "timeout": 90},
   {"id": "broken", "tool": "compile_latex_to_pdf", "args": {"latex_string": "\\documentclass{article}\\begin{document}\\undefinedmacro\\end{document"},
    "expect": ["(?i)error|failed"], "must_error": True, "timeout": 90}]},
 "conversion_mcp": {"tools": ["document_convert", "data_convert", "image_convert", "audio_convert", "video_convert", "archive_create", "archive_extract"], "cases": [
   {"id": "doc", "tool": "document_convert", "args": {"file_url": "{FIX}/doc.html", "from_format": "html", "to_format": "pdf"}, "reject": FAKE,
    "artifacts": [{"regex": P("pdf"), "pdf_text": ["Hello conversion"]}], "timeout": 120},
   {"id": "data", "tool": "data_convert", "args": {"file_url": "{FIX}/data.json", "from_format": "json", "to_format": "csv"}, "reject": FAKE,
    "artifacts": [{"regex": P("csv"), "contains": ["name", "alice", "78"], "min_size": 10}]},
   {"id": "image", "tool": "image_convert", "args": {"file_url": "{FIX}/sample.jpg", "from_format": "jpg", "to_format": "png"}, "reject": FAKE,
    "artifacts": [{"regex": P("png"), "image_size": [200, 200]}]},
   {"id": "audio", "tool": "audio_convert", "args": {"file_url": "{FIX}/tone.wav", "from_format": "wav", "to_format": "mp3"}, "reject": FAKE,
    "artifacts": [{"regex": P("mp3"), "duration": [1.8, 2.3]}], "timeout": 60},
   {"id": "video", "tool": "video_convert", "args": {"file_url": "{FIX}/sample.mp4", "from_format": "mp4", "to_format": "webm"}, "reject": FAKE,
    "artifacts": [{"regex": P("webm"), "duration": [5.5, 6.5]}], "timeout": 180},
   {"id": "zip", "tool": "archive_create", "args": {"file_urls": ["{FIX}/data.json", "{FIX}/doc.html"], "format": "zip"}, "reject": FAKE,
    "artifacts": [{"regex": P("zip"), "zip_entries": 2}]},
   {"id": "unzip", "tool": "archive_extract", "args": {"file_url": "{FIX}/bundle.zip", "format": "zip"}, "reject": FAKE,
    "artifacts": [{"regex": r"(/[\w./+-]+)", "dir_contains": ["data.json", "doc.html"]}]},
   {"id": "neg_path", "tool": "data_convert", "args": {"file_url": "/etc/passwd", "from_format": "json", "to_format": "csv"}, "expect": ["path not allowed"], "must_error": True},
   {"id": "neg_url", "tool": "document_convert", "args": {"file_url": "http://127.0.0.1:4002/v1/wallets", "from_format": "html", "to_format": "pdf"}, "expect": ["blocked private address"], "must_error": True}]},
 "ocr_mcp": {"tools": ["image_to_text", "pdf_to_text", "handwriting_ocr", "table_extraction", "math_ocr", "receipt_ocr", "barcode_reader"], "cases": [
   {"id": "image", "tool": "image_to_text", "args": {"image_url": "{FIX}/text.png"}, "expect": [r"(?i)hello\s*probe"], "reject": FAKE, "timeout": 120},
   {"id": "pdf", "tool": "pdf_to_text", "args": {"pdf_url": "{FIX}/probe.pdf"}, "expect": ["architecture"], "reject": FAKE, "timeout": 120},
   {"id": "hand", "tool": "handwriting_ocr", "args": {"image_url": "{FIX}/text.png"}, "expect": ["(?i)probe"], "reject": FAKE + ["Dear John"], "timeout": 120},
   {"id": "table", "tool": "table_extraction", "args": {"image_or_pdf_url": "{FIX}/table.png"}, "expect": ["Banana", r"0\.50"], "timeout": 120},
   {"id": "math", "tool": "math_ocr", "args": {"image_url": "{FIX}/math.png"}, "expect": [r"x\^\{?2", "7"], "reject": [r"\\int"], "timeout": 120},
   {"id": "receipt", "tool": "receipt_ocr", "args": {"image_url": "{FIX}/receipt.png"}, "expect": [r"45\.99", "(?i)probe mart"], "reject": ["Target"], "timeout": 120},
   {"id": "qr", "tool": "barcode_reader", "args": {"image_url": "{FIX}/qr.png"}, "expect": [r"https://probe\.local/abc"], "timeout": 60},
   {"id": "neg_url", "tool": "image_to_text", "args": {"image_url": "http://localhost:8980/health"}, "expect": ["blocked private address"], "must_error": True}]},
 "resume_mcp": {"tools": ["resume_score", "ats_check", "improve_resume", "resume_to_pdf", "cover_letter", "portfolio_generator"], "cases": [
   {"id": "score_a", "tool": "resume_score", "args": {"resume_text": RESUME_A}, "expect": [r"\d+/100"]},
   {"id": "score_b", "tool": "resume_score", "args": {"resume_text": RESUME_B}, "expect": [r"\d+/100"], "must_differ_from": "score_a"},
   {"id": "ats", "tool": "ats_check", "args": {"resume_text": RESUME_A, "job_description": JD}, "expect": ["Python", "(?i)missing.*Kubernetes"], "reject": ["Blockchain"]},
   {"id": "improve", "tool": "improve_resume", "args": {"resume_text": RESUME_A}, "expect": ["(?i)responsible for"]},
   {"id": "pdf", "tool": "resume_to_pdf", "args": {"resume_data": RESUME_A}, "reject": FAKE, "artifacts": [{"regex": P("pdf"), "pdf_text": ["Probe Person", "FastAPI"]}]},
   {"id": "cover", "tool": "cover_letter", "args": {"resume_text": RESUME_A, "job_description": JD}, "expect": ["Acme", "Probe Person"]},
   {"id": "portfolio", "tool": "portfolio_generator", "args": {"projects_data": "PayGate: x402 payment gateway for MCP tools\nChainView: Algorand block explorer"},
    "reject": FAKE, "artifacts": [{"regex": P("html"), "contains": ["PayGate", "ChainView"]}]}]},
 "pdf_mcp": {"tools": ["pdf_read_all", "pdf_search"], "cases": [
   {"id": "read", "tool": "pdf_read_all", "args": {"path": "{FIX}/probe.pdf"}, "expect": ["architecture"], "reject": ["404 Not Found"], "timeout": 120},
   {"id": "search", "tool": "pdf_search", "args": {"path": "{FIX}/probe.pdf", "query": "architecture"}, "expect": ["architecture"], "reject": ["404 Not Found"], "timeout": 120},
   {"id": "neg_path", "tool": "pdf_read_all", "args": {"path": "/etc/hostname"}, "expect": ["path not allowed"], "must_error": True}]},
 "pdf_reader_mcp": {"tools": ["read_pdf", "search_pdf", "pdf_evidence"], "cases": [
   {"id": "read", "tool": "read_pdf", "args": {"sources": [{"path": "{FIX}/probe.pdf"}]}, "expect": ["architecture"], "reject": ["'isError': True"]},
   {"id": "search", "tool": "search_pdf", "args": {"sources": [{"path": "{FIX}/probe.pdf"}], "query": "Summary"}, "expect": ["Summary"], "reject": ["'isError': True"]},
   {"id": "neg_path", "tool": "read_pdf", "args": {"sources": [{"path": "/etc/hostname"}]}, "expect": ["path not allowed"], "must_error": True},
   {"id": "evidence", "tool": "pdf_evidence", "args": {"operation": "inspect", "sources": [{"path": "{FIX}/probe.pdf"}]}, "expect": ["architecture"], "reject": ["'isError': True"]}]},
 "image_edit_mcp": {"tools": ["compress_image", "resize_image"], "cases": [
   {"id": "compress", "tool": "compress_image", "args": {"image_path": "{FIX}/sample.jpg", "quality": 40}, "artifacts": [{"regex": P("jpg")}]},
   {"id": "resize", "tool": "resize_image", "args": {"image_path": "{FIX}/sample.jpg", "width": 64, "height": 48}, "artifacts": [{"regex": P("png"), "image_size": [64, 48]}]},
   {"id": "missing", "tool": "resize_image", "args": {"image_path": "/nonexistent.jpg", "width": 10, "height": 10}, "expect": ["(?i)not found|error|404"], "must_error": True},
   {"id": "neg_path", "tool": "resize_image", "args": {"image_path": "/etc/passwd", "width": 10, "height": 10}, "expect": ["path not allowed"], "must_error": True}]},
 "video_edit_mcp": {"tools": ["trim_video"], "cases": [
   {"id": "trim", "tool": "trim_video", "args": {"video_path": "{FIX}/sample.mp4", "start_sec": 1.0, "end_sec": 3.0},
    "artifacts": [{"regex": P("mp4"), "duration": [1.7, 2.4]}], "timeout": 120},
   {"id": "neg_path", "tool": "trim_video", "args": {"video_path": "/etc/passwd", "start_sec": 1.0, "end_sec": 3.0}, "expect": ["path not allowed"], "must_error": True}]},
 "paper_mcp": {"tools": ["search_papers"], "cases": [
   {"id": "search", "tool": "search_papers", "args": {"query": "attention is all you need", "max_results": 2}, "expect": ['"title"', r"arxiv\.org"], "reject": ['"status": "error"'], "timeout": 90}]},
 "image_gen": {"tools": ["generate_image", "edit_image", "optimize_prompt", "analyze_image_quality", "get_hardware_status"], "cases": [
   {"id": "hw", "tool": "get_hardware_status", "args": {}, "expect": ["(?i)cpu"]},
   {"id": "optimize", "tool": "optimize_prompt", "args": {"prompt": "a red fox in snow"}, "expect": ["(?i)fox"]},
   {"id": "qa", "tool": "analyze_image_quality", "args": {"image_path": "{FIX}/sample.jpg"}, "expect": ["(?i)quality_score"]},
   {"id": "generate", "tool": "generate_image", "args": {"prompt": "a red fox in snow", "steps": 4},
    "expect": ['"status": "success"', '"backend": "diffusers:'], "reject": ["fast_test_placeholder"],
    "artifacts": [{"regex": r'"file_path": "([^"]+)"', "min_size": 100000}], "timeout": 900},
   {"id": "neg_path", "tool": "analyze_image_quality", "args": {"image_path": "/etc/passwd"}, "expect": ["path not allowed"], "must_error": True},
   {"id": "edit", "tool": "edit_image", "args": {"image_path": "{FIX}/sample.jpg", "prompt": "make it snowy", "steps": 2},
    "expect": ['"success"|"status": "success"'], "timeout": 900}]},
}

out = Path(__file__).resolve().parent / "test_matrix.json"
out.write_text(json.dumps(M, indent=1))
print(f"wrote {out} ({sum(len(v['cases']) for v in M.values())} cases, {len(M)} domains)")
