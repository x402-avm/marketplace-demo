# AGENTS.md

Practical guidance for AI coding agents and human contributors working on `marketplace-demo`.

## Project Overview

`marketplace-demo` is a reference integration demonstrating how autonomous AI agents and users discover, purchase, and consume payment-gated Model Context Protocol (MCP) services on Algorand LocalNet.

### Source Tree Layout

- `chain/`: LocalNet orchestration scripts.
  - `bootstrap.py`: Creates vendor, treasury, and client accounts, mints the mUSD asset, funds accounts via KMD.
  - `gen_listings.py`: Generates the active listing catalog schema in `servers/marketplace.json`.
  - `tests/`: Offline and simulated market unit tests.
- `marketplace/`:
  - `gateway/`: FastAPI reverse proxy and quote coordination service.
    - `app/proxy.py`: Dynamic routing and 402 challenge forwarding to backend MCP servers.
    - `app/passes.py`: Unsigned transaction quote generator for vendor passes and subscriptions.
    - `app/faucet.py`: Rate-limited dispenser for LocalNet ALGO and mUSD.
    - `tests/`: Offline, security, and live integration test suites.
  - `web/`: React 18, TypeScript, and Vite single-page application.
    - `src/`: UI components, catalog grid, wallet connector, and tool execution runner using `x402-avm-js`.
  - `start.sh`, `status.sh`, `stop.sh`: Service orchestration scripts.
- `servers/`: 16 FastMCP server domains spanning 64 paid tools with `ai-economy-sdk` `PaymentGate` middleware.
  - `tts/download_models.sh`: Utility to fetch Kokoro ONNX model weights and voice embeddings.
- `THIRD_PARTY_NOTICES.md`: Licenses for third-party libraries and model assets.

## Setup Commands

### Python Environment (Gateway & Chain)

```bash
uv venv -q --python 3.12 .venv
source .venv/bin/activate
uv pip install -r marketplace/gateway/requirements.txt
uv pip install py-algorand-sdk pytest pytest-asyncio
```

### Node.js Environment (Web Frontend)

```bash
cd marketplace/web
npm install
```

## Running Tests

### 1. Gateway Offline & Security Tests

Run the gateway offline test suite and security vulnerability checks:

```bash
cd marketplace/gateway
pytest tests/test_offline.py tests/test_security.py
```

### 2. Chain Offline Tests

Run unit tests for chain utility scripts:

```bash
cd chain
pytest tests/
```

### 3. Web Frontend Typecheck & Tests

Verify TypeScript compilation and run Vitest unit tests:

```bash
cd marketplace/web
npm run build
npm test
```

### 4. Full Integration Tests (Requires Running LocalNet)

When LocalNet and MCP service domains are running (`./start.sh`):

```bash
cd marketplace/gateway
LOCALNET=1 pytest tests/test_live.py tests/test_paid_live.py
```

## Code Style and Conventions

- **Paths**: Never hardcode absolute system paths or usernames. Always resolve paths relative to the current file or repository root via `pathlib.Path(__file__).resolve()`.
- **Network Identifiers**: Use CAIP-2 Algorand format (`algorand:<genesis_hash>`).
- **Currency Units**:
  - Native ALGO is denominated in microAlgos (`1 ALGO = 1_000_000 microAlgos`).
  - mUSD (Micro-USD ASA) is configured with 6 decimals (`1 mUSD = 1_000_000 base units`).
- **Payment Invariants**:
  - Micropayments must follow settle-on-success semantics: callers pay only when tool execution succeeds.
  - Vendor passes grant unlimited calls to a scoped vendor or listing without additional per-call fees.
- **Secrets & Sensitive State**:
  - Never commit `accounts.json`, mnemonics, private keys, or `.run/` PID files.
  - Faucet and quote endpoints must never return private keys or mnemonic secrets.

## What Not to Touch

- Do not alter the core x402 payment challenge format (`x402Version`, `accepts`, `network`, `amount`).
- Do not bypass rate limiting or input sanitization in `marketplace/gateway/app/faucet.py` and `app/proxy.py`.
- Do not hardcode specific vendor addresses into gateway routing logic; always read from the active catalog.

## Pull Request Checklist

Before submitting a pull request:
1. Ensure gateway offline tests and security tests pass: `pytest marketplace/gateway/tests/test_offline.py marketplace/gateway/tests/test_security.py`.
2. Ensure chain offline tests pass: `pytest chain/tests/`.
3. Ensure frontend builds and passes tests: `cd marketplace/web && npm run build && npm test`.
4. Verify no personal names or absolute paths remain: `grep -rn "/usr/local\|/opt" .` style scans return only intended references.
5. Verify `.github/workflows/ci.yml` is valid YAML.
