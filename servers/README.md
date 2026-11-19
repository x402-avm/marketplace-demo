# Algorand MCP Server Ecosystem

This directory hosts the distributed Model Context Protocol (MCP) server fleet for the Algorand development ecosystem, providing specialized tools across 16 domains.

---

## 1. Architecture

The ecosystem implements a **Centralized Runtime + Distributed Thin-Proxy** pattern:

- **Isolated Virtual Environments**: Each domain has its own independent Python virtual environment (`<domain>/venv`), preventing package conflicts and keeping individual dependencies modular.
- **Centralized Runtime (FastAPI)**: Each domain runs a core backend server (`runtime_server.py`) bound to `127.0.0.1`. The runtime performs heavy execution tasks (e.g. running native compilers, invoking browser automation, executing sandboxed code, extracting text, generating PDF invoices, or calling media tools).
- **Thin Proxies (FastMCP over SSE)**: Each domain exposes 2 to 5 lightweight FastMCP proxy processes (`mcp_server_1.py`, `mcp_server_2.py`, etc.) bound to `127.0.0.1` that serve clients via Server-Sent Events (SSE). When an MCP client invokes a tool, the proxy forwards the request to the local runtime and streams back the structured response.
- **Canonical Topology**: Port numbers, proxy counts, and server relationships are strictly defined in [`topology.json`](topology.json), spanning ports 8050 to 8130 (skipping 8080) and 10000/10002–10004 for GPU image generation.

---

## 2. Starting and Stopping Services

All domain processes run in their own session groups; process IDs are tracked in `tests/run/<domain>.pids` to ensure clean, isolated process control.

### Single Domain Management
Use `tools/domainctl.sh` to manage individual domains:
```bash
# Start a domain (starts runtime and all proxies)
tools/domainctl.sh up <domain>

# Stop a domain (terminates runtime and all proxies cleanly)
tools/domainctl.sh down <domain>

# Check listening status of runtime and proxy ports
tools/domainctl.sh status <domain>
```

### Fleet-Wide Management
- **Start All**: `./start_all.sh [domain ...]`
  Iterates through domains in `topology.json` order (or specified domains), launches each via `domainctl.sh up`, passes environment variables through (e.g. `PAYMENTS=on`), provides special handling for `image_gen` (`FAST_TEST_MODE=1`, `RUNTIME_WAIT=600`), and outputs a status table.
  ```bash
  # Start all 16 domains
  ./start_all.sh

  # Start with Algorand micropayments enabled
  PAYMENTS=on ./start_all.sh

  # Start specific domains
  ./start_all.sh tts web_mcp
  ```

- **Stop All**: `./stop_all.sh [domain ...]`
  Stops all running domains (or specified domains) using `domainctl.sh down` without using indiscriminate commands like `pkill`.
  ```bash
  ./stop_all.sh
  ```

---

## 3. Testing and Verification

- **Individual Domain Probe**:
  `tools/probe.py` validates SSE connections, tool listing, tool invocations, and artifact outputs against expectations in `tools/test_matrix.json`.
  ```bash
  <domain>/venv/bin/python tools/probe.py <domain> --json tests/outputs/probe/<domain>.json
  ```
- **Automated Fleet-Wide Probes**:
  `tools/run_all_probes.sh` automates the start -> probe -> stop lifecycle across all domains (by default all domains except `image_gen` unless specified), formats results, outputs a summary table, and writes to `tests/outputs/probe/SUMMARY.md`:
  ```bash
  # Probe all domains (default set)
  tools/run_all_probes.sh

  # Probe specific domains
  tools/run_all_probes.sh tts web_mcp pdf_mcp

  # Pass extra arguments to probe.py (e.g. testing with payments)
  tools/run_all_probes.sh tts -- --paid
  ```
- **Test Matrix Generation**:
  Test definitions and assertions are stored in `tools/test_matrix.json` and generated/updated using `tools/gen_matrix.py`.

### Unified Test Suite (`test_all.sh`)
The root-level script `test_all.sh` executes the entire verification pipeline in sequence and outputs a final PASS/FAIL summary table:
1. **SDK**: Runs pytest on `ai_economy_package` against Algod LocalNet.
2. **x402 Fork**: Runs pytest on `x402_package` against Algod LocalNet.
3. **Chain Integrity**: Validates the block hash-chain via `chain/explorer.py verify`.
4. **Free Probes**: Probes all 16 domains (free tool calls) via `servers/tools/run_all_probes.sh`.
5. **Paid Probes**: Probes all 16 domains with micropayments enabled (`PAYMENTS=on`).
6. **Economy Demo**: Runs the end-to-end multi-agent economy simulation `test_economy.py`.

**Options:**
- `--quick`: Runs steps 1–3 only (SDK, x402 fork, chain verify), skipping probe and demo steps.
- `--no-paid`: Runs all steps except step 5 (skips paid probes).

```bash
# Full test suite (all 6 steps)
./test_all.sh

# Quick verification (steps 1-3 only)
./test_all.sh --quick

# Full suite without paid probes (skips step 5)
./test_all.sh --no-paid
```

### Probe Verification Matrix (`tools/probe.py`)
`tools/probe.py` validates SSE connections, tool listing, tool invocations, and artifact outputs against expectations in `tools/test_matrix.json`.
Supported test matrix assertion keys:
- `expect`: Substring expected in tool response.
- `reject`: Substring that must NOT appear in response.
- `allow_error`: Boolean; if true, allows tool execution error.
- `must_error`: Boolean; requires tool invocation to report error (`isError=True` / `ToolError`).
- `artifacts`: Map of output file assertions:
  - `pdf_text`: Text substring expected in generated PDF.
  - `contains`: Substring expected in artifact text file.
  - `zip_entries`: Files expected inside generated zip archive.
  - `duration`: Audio/video duration range verification.
  - `image_size`: Expected image dimension tuple `[width, height]`.
  - `min_size`: Minimum byte size required for output files.
  - `regex`: Regular expression pattern match against artifact contents.
  - `dir_contains`: List of files expected in output directory.

### Outputs Cleanup (`tools/clean_outputs.sh`)
Maintenance utility to clean up generated artifacts, images, and probe results:
- Scans strictly inside `servers/*/outputs/` and `servers/tests/outputs/probe/`.
- Deletes files older than N days (`find -mindepth 1 -mtime +N`), protecting original test fixtures and other directories.
- Prints each removed file and outputs a summary of reclaimed disk space.

**Options:**
- `--days N`: Specify age threshold in days (default: `7`).
- `--dry-run`: Preview files to be removed without deleting them.

```bash
# Preview files older than 7 days that would be deleted
tools/clean_outputs.sh --dry-run

# Clean files older than 14 days
tools/clean_outputs.sh --days 14
```

---

## 4. Algorand Micropayments Integration

The ecosystem provides native, on-chain micropayment gating for MCP tool calls using the Algorand blockchain and the `x402` payment standard.

### Unified Proxy Architecture
All 16 domains follow a single canonical pattern:
- **`proxy.py`**: Declares FastMCP tools and handles execution logic for the domain.
- **`mcp_server_N.py`**: Lightweight 4-line launchers delegating to `servers/common/paid.py:serve(mcp, domain, index)`.
- **Operating Modes**:
  - `PAYMENTS=off` (default): FastMCP proxies serve clients over standard, free Server-Sent Events (SSE).
  - `PAYMENTS=on`: Proxies wrap FastMCP with `PaymentGate` middleware, requiring on-chain payment settlement before granting access to paid tools.
  - *Status*: All 16 domains are payment-enabled and verified. For `image_gen`, real backend diffusers `stabilityai/sd-turbo` (GPU if available, else CPU); `FAST_TEST_MODE` placeholder only for tests; see `image_gen/README.md`.

### Pricing Structure & Facilitator Fee Floor
Tool pricing is centrally declared in [`pricing.json`](pricing.json) in microAlgos:
- **Floor Requirement**: Every tool price is set to **at least 3,000 microAlgos** (default `3000`).
- **Fee Economics**: When settling a tool call, the server acts as fee payer for a 2-transaction atomic group (client payment txn + server zero-amount fee-payer txn), costing `2 x 1,000 = 2,000 microAlgos` in network transaction fees.
- **Fee Floor Enforcement**: `PaymentGate` automatically calculates `fee_cost = 2 * min_fee_per_txn` (2,000 microAlgos). During startup, any price `<= fee_cost` raises `ValueError` unless `allow_loss=True`. In addition, `price_for()` clamps discounted prices to `fee_cost + 1` (2,001 microAlgos) with a single warning log per tool.
- **Real-World Execution Example**:
  - On a 6,000 microAlgo tool (e.g. `latex_mcp` or `ocr_mcp`):
    `paid=6000 fee=2000 net=4000`
  - On a 3,000 microAlgo lookup (e.g. `paper_mcp` or `domain_mcp`):
    `paid=3000 fee=2000 net=1000`

### Cryptographic Identity & Discounts
- **Caller Authentication**: Client requests provide zero-cost off-chain proof of wallet ownership using Ed25519-signed headers (`x-sender-address`, `x-sender-timestamp`, `x-sender-signature`). Signatures are validated against the claimed Algorand address with a strict 120-second timestamp skew limit. Plain, unsigned caller addresses are ignored.
- **Subscriptions**: Callers holding the `AI-SUB` ASA (asset ID in `chain/accounts.json`) transferred within the last 30 days receive free access (`price = 0`).
- **Bulk Usage Discounts**: Callers who paid `> 1,000,000 microAlgos` (> 1 ALGO) in the trailing 30 days automatically receive a 50% discount on tool calls (the fee floor still guarantees profitability).

### Security & Protection Architecture
- **Charge Only on Success**: `PaymentGate` inspects tool execution responses (`gate.py:80-110`). On tool failure (`isError=True` or `ToolError`), payment settlement is aborted, the signed transaction is discarded, and the caller is never charged on-chain. All 15 thin proxies raise `ToolError` on failure so errors are never billed.
- **Replay Protection**: `PaymentGate` validates payment hashes against a `ReplayStore` (`replay.py`). Production domain proxies share a SQLite replay store with WAL mode at `servers/tests/run/replay_<domain>.sqlite` (`servers/common/paid.py:50`), preventing replay attacks across multiple proxy workers.
- **Safety Allow-lists**:
  - **Filesystem Paths**: `servers/common/paths.py:14-50` (`safe_path`) restricts file access to approved directories (`servers/`, outputs, temp), rejecting traversal attempts with `PathNotAllowed("path not allowed")`.
  - **SSRF & Network Guard**: `servers/common/netguard.py:15-55` (`check_url`) inspects requested endpoints and blocks private, loopback, link-local, and cloud metadata IP ranges with `BlockedURL("blocked private address")`.

### Verification Commands
Verify payments across individual domains or the entire fleet:
```bash
# 1. Exact paid probe on a single domain (creates fresh funded payer and verifies on-chain delta)
PAYMENTS=on tools/domainctl.sh up paper_mcp
paper_mcp/venv/bin/python tools/probe.py paper_mcp --paid
tools/domainctl.sh down paper_mcp

# 2. Automated fleet probe
tools/run_all_probes.sh

# 3. Fleet Agent Demo (runs autonomous paying agent across domains)
tools/agent_demo.py --start

# 4. Verify blockchain hash-chain integrity
python ../chain/explorer.py verify

# 5. Run full SDK test suite against LocalNet
cd ../ai_economy_package && LOCALNET=1 python -m pytest tests -q
```

---

## 5. Domain Topology and Tools Matrix

| Domain Name | Runtime Port | Proxy Ports | Tools (`test_matrix.json`) | Backend Technology |
| :--- | :--- | :--- | :--- | :--- |
| **tts** | 8050 | 8051, 8052, 8053, 8054 | `synthesize_speech` | Kokoro TTS / ONNX, soundfile, phonemizer |
| **image_gen** | 10000 | 10002, 10003, 10004 | `generate_image`, `edit_image`, `optimize_prompt`, `analyze_image_quality`, `get_hardware_status` | Stable Diffusion, PyTorch / CUDA, Diffusers |
| **web_mcp** | 8059 | 8060, 8061, 8062, 8063 | `web_open_page`, `web_screen_shoot`, `web_page_info`, `web_click_button`, `send_api_request`, `ddg_search` | Playwright (headless Chromium), DuckDuckGo, httpx |
| **invoice_mcp** | 8064 | 8065, 8066, 8067, 8068, 8069 | `generate_invoice` | ReportLab PDF engine, Python |
| **domain_mcp** | 8070 | 8071, 8072, 8073, 8074 | `domain_whois`, `domain_dns`, `domain_ssl`, `domain_ip` | python-whois, dnspython, cryptography (TLS socket inspection) |
| **yt_mcp** | 8075 | 8076, 8077, 8078, 8079 | `download_yt_video`, `get_yt_transcript` | yt-dlp, youtube-transcript-api |
| **sandbox_mcp** | 8081 | 8082, 8083, 8084, 8085, 8086 | `run_sandbox_code` | Subprocess container/jail (Python, Node.js, GCC, G++, Java) |
| **latex_mcp** | 8087 | 8088, 8089, 8090 | `compile_latex_to_pdf` | pdflatex, latexmk, TeX Live distribution |
| **conversion_mcp** | 8091 | 8092, 8093, 8094, 8095 | `document_convert`, `data_convert`, `image_convert`, `audio_convert`, `video_convert`, `archive_create`, `archive_extract` | Pandoc, Pillow, LibreOffice, FFmpeg, tarfile/zipfile |
| **ocr_mcp** | 8096 | 8097, 8098 | `image_to_text`, `pdf_to_text`, `handwriting_ocr`, `table_extraction`, `math_ocr`, `receipt_ocr`, `barcode_reader` | Tesseract OCR (pytesseract), PyMuPDF (fitz) |
| **resume_mcp** | 8099 | 8100, 8101, 8102, 8103, 8104 | `resume_score`, `ats_check`, `improve_resume`, `resume_to_pdf`, `cover_letter`, `portfolio_generator` | spaCy, scikit-learn, ReportLab |
| **pdf_mcp** | 8105 | 8106, 8107, 8108, 8109, 8110 | `pdf_read_all`, `pdf_search` | PyMuPDF, FastEmbed (BGE embeddings ONNX Runtime) |
| **pdf_reader_mcp** | 8111 | 8112, 8113 | `read_pdf`, `search_pdf`, `pdf_evidence` | Native Rust MCP engine (`pdf-reader-core` stdio binary) |
| **image_edit_mcp** | 8114 | 8115, 8116, 8117, 8118 | `compress_image`, `resize_image` | Pillow (PIL) |
| **video_edit_mcp** | 8119 | 8120, 8121, 8122, 8123, 8124 | `trim_video` | FFmpeg subprocess / MoviePy |
| **paper_mcp** | 8125 | 8126, 8127, 8128, 8129, 8130 | `search_papers` | arXiv REST API, XML ElementTree parser |
