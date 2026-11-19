# Changelog

All notable changes to the `marketplace-demo` project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.1] - 2026-11-18

### Changed
- **Individual Vendor Passes**: Replaced global subscription model with vendor-scoped and listing-scoped passes (`x402-pass:listing:<id>` and `x402-pass:vendor:<id>`).
- **Pass Quote Endpoint**: Updated Gateway `POST /api/passes/quote` to construct unsigned payments directly to the vendor with scope notes.
- **Pass Verification**: Configured `PaymentGate` on all 16 MCP service domains to evaluate active passes via `ChainReader`.

### Removed
- Removed legacy global subscription swap endpoints (`/api/subscription/*`).

## [0.3.0] - 2026-11-18

### Added
- **FastAPI Marketplace Gateway (`marketplace/gateway/`)**: Reverse proxy coordinating 16 FastMCP backend domains, quote construction, LocalNet faucet, rate limiting, and 402 challenge relay.
- **React & TypeScript Web UI (`marketplace/web/`)**: Interactive tool explorer and runner powered by `x402-avm-js`, supporting ALGO and mUSD micropayments, wallet integration, and pass purchases.
- **Chain Orchestration (`chain/`)**: LocalNet provisioning scripts (`bootstrap.py`), mUSD asset creation, deterministic listing generator (`gen_listings.py`), and market simulation tools (`simulate_market.py`).
- **16 MCP Service Domains (`servers/`)**: 64 payment-gated AI tools across 4 vendors (Nova Labs, Blue Fern AI, Quarry Compute, Lumen Works).
- **One-Command Lifecycle Scripts**: `./start.sh`, `./status.sh`, and `./stop.sh` managing the full local environment.
