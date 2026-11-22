# marketplace-demo

[![CI](https://github.com/x402-avm/marketplace-demo/actions/workflows/ci.yml/badge.svg)](https://github.com/x402-avm/marketplace-demo/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**A working marketplace where people and programs buy AI tools per call, on Algorand LocalNet.**

Four independent vendors sell 64 tools, from PDF reading and OCR to code sandboxes and image generation, each priced per call. Shoppers pay from a wallet in the browser, or buy a pass and call for free for 30 days. A scripted agent (`servers/tools/agent_demo.py`) calls tools across every vendor and pays for each call itself. Every payment is a real Algorand transaction on your machine, and nothing is charged when a tool fails.

It shows all three [x402-avm](https://github.com/x402-avm/x402-avm) packages working together: the vendors use [`ai-economy-sdk`](https://github.com/x402-avm/ai-economy-sdk) (which builds on [`x402-algorand`](https://github.com/x402-avm/x402-algorand)), and the web app pays with [`x402-avm-js`](https://github.com/x402-avm/x402-avm-js).

> **This is a demo, not a product.** It runs on LocalNet only, with test money and dispenser-funded accounts. Use it to see the pieces working together, then build on the packages. Don't deploy it as it is.

## Architecture

```mermaid
flowchart TD
    subgraph Clients["Clients"]
        UI["Web UI (React + x402-avm-js)"]
        Agent["Autonomous AI Agent (ai-economy-sdk client)"]
    end

    subgraph Marketplace["Marketplace Gateway (:8800)"]
        GW["FastAPI Gateway"]
        Catalog["Listing Catalog & Search"]
        Quote["Pass & Quote Builder"]
        Faucet["LocalNet Faucet"]
    end

    subgraph Vendors["16 MCP Service Domains (:8001-:8016)"]
        VA["Vendor A: Nova Labs (ALGO)"]
        VB["Vendor B: Blue Fern AI (mUSD)"]
        VC["Vendor C: Quarry Compute (ALGO)"]
        VD["Vendor D: Lumen Works (ALGO)"]
    end

    subgraph Algorand["Algorand LocalNet"]
        Algod["Algod Node (:4001)"]
        KMD["KMD Wallet (:4002)"]
        Indexer["Indexer (:8980)"]
    end

    UI -->|HTTP / REST| GW
    Agent -->|x402 Protocol| GW
    GW -->|Proxy Paid Tool Calls| Vendors
    GW -->|Balances & Signatures| Algorand
    Vendors -->|Settle Payments on Success| Algorand
```

## Service Catalog Overview

The marketplace deploys 64 listings partitioned across 4 vendors and 16 MCP service domains, configured via `servers/marketplace.json`:

### Vendors

- **Vendor A (`vendorA` — Nova Labs)**:
  - **Accepted Asset**: Native ALGO (Asset ID `0`)
  - **Vendor Address**: `A4ZN6Y7WO2SJ2NA33IERUZWC476MCMTX6JA5CM2XC27ZS2OIB43F24TCWE`
  - **Listings**: 22 listings across 16 domains
  - **Vendor Pass**: `vendor:vendorA` at 8,100,000 microALGO (8.1 ALGO) for 30-day access
- **Vendor B (`vendorB` — Blue Fern AI)**:
  - **Accepted Asset**: mUSD (Test ASA Asset ID `1009`)
  - **Vendor Address**: `DCOWE3GVBN4CZZCAQCWZFT32NMMCRI7Z75INX7NBWSS2ARO5QYVH7VJJDI`
  - **Listings**: 16 listings across 16 domains
  - **Vendor Pass**: `vendor:vendorB` at 4,870,000 micro-mUSD (4.87 mUSD) for 30-day access
- **Vendor C (`vendorC` — Quarry Compute)**:
  - **Accepted Asset**: Native ALGO (Asset ID `0`)
  - **Vendor Address**: `A2JRGNJ7ZGLU63EGNMKNG5TXQAVN232SP6SOFMHADF3VUUBNTD6FJ4Q2WA`
  - **Listings**: 14 listings across 14 domains
  - **Vendor Pass**: `vendor:vendorC` at 6,740,000 microALGO (6.74 ALGO) for 30-day access
- **Vendor D (`vendorD` — Lumen Works)**:
  - **Accepted Asset**: Native ALGO (Asset ID `0`)
  - **Vendor Address**: `JP2QTD7KUY3KVP57ALY3CQN3I3MOVB2HSTGHSXON2PDZ2FNUO5SL4W4TJ4`
  - **Listings**: 12 listings across 12 domains
  - **Vendor Pass**: `vendor:vendorD` at 6,880,000 microALGO (6.88 ALGO) for 30-day access

### Treasury & Subscription Passes

- **Treasury Address**: `SPDMDX4SBNY35L2GZB7RBKTPRT76NUVWA2GNXEQDTPPNKUOYJIK5ERFAW4`
- **Pass Validity**: 30 days
- **Note Prefix**: `x402-pass:` (e.g. `x402-pass:vendor:vendorA` or `x402-pass:listing:<id>`)
- **Service Pass Pricing**: 80x per-call tool multiple (minimum 100,000 micro-units)
- **Vendor Pass Share**: 60% of total service pass sum
- **Pass Verification**: Proved with a client wallet-signed, off-chain identity transaction (`X-Identity-Txn`)

### MCP Server Domains (16 Service Domains)

- **`conversion_mcp`** (4 proxies): Archive, audio, data, document, image, and video format conversion.
- **`domain_mcp`** (4 proxies): Domain intelligence (WHOIS, DNS records, SSL certificates, IP resolution).
- **`image_edit_mcp`** (4 proxies): Image compression and resizing tools.
- **`image_gen`** (3 proxies): Local AI image generation, editing, and prompt optimization.
- **`invoice_mcp`** (5 proxies): Structured JSON-to-PDF invoice generation with ReportLab.
- **`latex_mcp`** (3 proxies): Academic and mathematical LaTeX compilation to PDF.
- **`ocr_mcp`** (2 proxies): Document OCR, handwriting recognition, math OCR, table extraction, and barcode reading.
- **`paper_mcp`** (5 proxies): Academic paper and preprint search across scientific repositories.
- **`pdf_mcp`** (5 proxies): PDF document searching and full-text extraction.
- **`pdf_reader_mcp`** (2 proxies): PDF evidence extraction and chunked document reading.
- **`resume_mcp`** (5 proxies): Resume scoring, ATS optimization, cover letter generation, and portfolio formatting.
- **`sandbox_mcp`** (5 proxies): Multi-language isolated code execution sandbox (Python, Java, Node.js, C, C++).
- **`tts`** (4 proxies): Kokoro ONNX neural speech synthesis runtime.
- **`video_edit_mcp`** (5 proxies): Video trimming and stream processing tools.
- **`web_mcp`** (4 proxies): Web browsing, DuckDuckGo search, DOM interaction, and screenshot capture.
- **`yt_mcp`** (4 proxies): YouTube video downloading and transcript extraction with yt-dlp.

## Requirements

- Python 3.10+ (Python 3.12 recommended)
- Node.js 22.12+ (or newer) and npm (for the web application)
- Docker and [AlgoKit CLI](https://github.com/algorandfoundation/algokit-cli) (for LocalNet)
- `curl`

## Quickstart

### 1. Start LocalNet

Ensure Docker is running, then start the Algorand LocalNet instance:

```bash
algokit localnet start
```

### 2. Run Setup

Run the one-command setup script to create a virtual environment and install all dependencies:

```bash
./setup.sh
```

### 3. Start the Marketplace

Launch the gateway, all 16 MCP service domains, and the web UI:

```bash
./start.sh
```

This script performs the following initialization steps:
1. Verifies Algorand LocalNet health on ports 4001 (Algod), 4002 (KMD), and 8980 (Indexer).
2. Bootstraps LocalNet accounts, mints the mUSD test asset, and funds vendor accounts.
3. Generates the active listing catalog (`servers/marketplace.json`).
4. Starts all 16 MCP service domains in the background.
5. Starts the FastAPI gateway on `http://localhost:8800`.
6. Launches the Vite development server on `http://localhost:5173`.

### 4. Check Status and Stop

Inspect running services and port bindings:

```bash
./status.sh
```

To stop all services:

```bash
./stop.sh
```

<!-- screenshots: added by orchestrator -->

## Testing

### Gateway Offline and Security Tests

Run the gateway offline test suite and security controls without external dependencies:

```bash
cd marketplace/gateway
pytest tests/test_offline.py tests/test_security.py
```

### Chain Scripts Tests

Run unit tests for chain utility scripts:

```bash
cd chain
pytest tests/
```

### Web Frontend Tests and Typecheck

Run TypeScript typechecking and Vitest unit tests:

```bash
cd marketplace/web
npm run build
npm test
```

### Full Integration Tests (Requires LocalNet)

When LocalNet and MCP servers are running:

```bash
cd marketplace/gateway
LOCALNET=1 pytest tests/test_live.py tests/test_paid_live.py
```

## Repository Structure

```
marketplace-demo/
├── chain/                  # Algorand LocalNet bootstrap, listing generation, and tests
├── marketplace/
│   ├── gateway/            # FastAPI reverse proxy, quote engine, and faucet
│   ├── web/                # React / TypeScript frontend utilizing x402-avm-js
│   ├── start.sh            # Service orchestration startup script
│   ├── status.sh           # Service health checker
│   └── stop.sh             # Graceful shutdown script
├── servers/                # 16 payment-gated FastMCP server domains
├── THIRD_PARTY_NOTICES.md  # Third-party licensing documentation
├── AGENTS.md               # Instructions for autonomous AI coding agents
├── LICENSE                 # MIT License
└── README.md
```

## Related Repositories

- [ai-economy-sdk](https://github.com/x402-avm/ai-economy-sdk) - Python MCP payment gateway SDK
- [x402-algorand](https://github.com/x402-avm/x402-algorand) - Algorand payment scheme plugin for x402
- [x402-avm-js](https://github.com/x402-avm/x402-avm-js) - TypeScript/JavaScript client for x402 Algorand payments
- [examples](https://github.com/x402-avm/examples) - Runnable examples on LocalNet, TestNet, and MainNet
- [Documentation](https://x402-avm.github.io) - Complete architecture and protocol guides

## Licences

The `marketplace-demo` repository is licensed under the [MIT License](LICENSE) (Copyright (c) 2026 x402-avm contributors).

The `ocr_mcp` and `pdf_mcp` services use [PyMuPDF](https://github.com/pymupdf/PyMuPDF), which is licensed under the GNU Affero General Public License v3.0 ([AGPL-3.0](https://www.gnu.org/licenses/agpl-3.0.html)). Deploying or hosting those specific services over a network requires complying with the AGPL-3.0 terms (or obtaining a commercial license from Artifex). The underlying SDKs (`ai-economy-sdk`, `x402-algorand`, and `x402-avm-js`) do not depend on PyMuPDF.

For full details on all third-party dependencies, model assets, and vendored code, see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
