# Algorand AI Service Marketplace

A decentralized AI agent and tool marketplace powered by the Algorand Virtual Machine (AVM) and the x402 payment protocol. The marketplace enables autonomous agents and web users to discover, pay for, and execute specialized Model Context Protocol (MCP) tools across 16 domains with instant on-chain settlement, gasless transactions via fee abstraction, subscription passes, and tier-based discounts.

---

## 1. Overview & Architecture

### Key Components
- **Vendors (`vendorA`, `vendorB`, `vendorC`, `vendorD`)**: Independent service providers operating 64 MCP server proxies across 16 domains. Vendors receive payments directly into their Algorand accounts.
- **MCP Service Domains (16 Domains, 64 Proxies)**: Tools spanning speech synthesis (`tts`), code execution (`sandbox_mcp`), LaTeX rendering (`latex_mcp`), PDF manipulation, invoice processing, image editing, and more.
- **Gateway API (FastAPI, Port 8800)**: Facilitates catalog discovery, tool routing, SSE streaming, account history, faucet, and subscription swaps. The gateway **never** holds private keys and never signs on behalf of users.
- **Marketplace Web UI (React + Vite, Port 5173)**: Interactive browser interface supporting Lute wallet, KMD dev wallet, and mnemonic accounts, powered by the `x402-avm-js` client library.

### Payment Modes
1. **Per-Call ALGO**: Native microAlgos payment (x402 exact scheme, asset 0).
2. **Per-Call mUSD**: Algorand Standard Asset (ASA) pegged stablecoin payment (asset ID 3456).
3. **Passes (individual, per vendor)**: a pass is one payment straight to a vendor with the note `x402-pass:<scope>`. Two scopes exist: `listing:<id>` (one service of that vendor) and `vendor:<id>` (all of that vendor's services). Prices are in `servers/marketplace.json` (`listings[].pass`, `vendors[].pass`). A pass is valid for 30 days and only at the vendor that was paid; the caller proves ownership with a wallet-signed, never-submitted identity transaction (`X-Identity-Txn`). There is no marketplace-wide pass.
4. **Bulk Discounts**: Historical high-volume consumers receive automated tiered discounts verified by on-chain transaction history.
5. **Settle-on-Success**: Failed tool executions are never settled; users are never charged for tool failures.

### Architecture & Money Flow Diagram

```text
+-----------------------------------------------------------------------------------+
|                                  USER / AGENT                                     |
|  [ Browser Web UI :5173 ]  or  [ Autonomous Python/TS Client ]                    |
|  Wallets: Lute Extension | KMD Dev Wallet | Local Dev Mnemonic                     |
+-----------------------------------------------------------------------------------+
       |                                                               |
       | 1. HTTP Tool Call (Anonymous)                                 | 3. Signs Payment Txn
       v                                                               |    (or Identity Proof)
+-----------------------------------------+                            |
|             GATEWAY (:8800)             |                            |
| - Routes to proxy                       |                            |
| - Returns 402 PAYMENT-REQUIRED          |                            |
| - Never holds keys / Never signs funds  |                            |
+-----------------------------------------+                            |
       |                                                               |
       | 2. Proxies Request                                            |
       v                                                               |
+----------------------------------------------------+                 |
|             VENDOR PROXY (MCP Server)              |<----------------+
| - Verifies x402 signature & atomic group           |  4. Retries Call with
| - If valid: executes runtime MCP tool              |     PAYMENT-SIGNATURE
| - Settle-on-success: submits group to Algorand     |
+----------------------------------------------------+
       |                              |
  Executes tool                       | 5. Settles Payment Group
       v                              v
+---------------+         +-----------------------------------------------+
|    RUNTIME    |         |            ALGORAND BLOCKCHAIN                |
|    SERVER     |         |  (LocalNet: Algod :4001, Indexer :8980)       |
+---------------+         |                                               |
                          |  Direct Transfer: [User -> Vendor Account]    |
                          |  Fee Payer: Vendor covers network fees (0 gas)|
                          +-----------------------------------------------+
```

---

## 2. Quick Start

### Prerequisites
- Python 3.12 with `.venv` at repository root
- Node.js $\ge$ 20 and npm
- Algorand LocalNet running via AlgoKit:
  ```bash
  algokit localnet start
  ```

### Start the Marketplace
Launch LocalNet check, account bootstrapping, 16 MCP service domains, Gateway API, and Web UI with a single command:
```bash
./start.sh
```

Flags available:
- `--domains d1,d2,...`: Start a specific subset of service domains (e.g. `--domains tts,sandbox_mcp,latex_mcp`).
- `--no-web`: Start backends and gateway without opening the Vite Web UI.
- `--no-paid`: Start MCP proxies in unpaid mode (`PAYMENTS=off`).

### Check System Status
View status across LocalNet, all 16 domains, Gateway, and Web UI:
```bash
./status.sh
```

### Stop the Marketplace
Gracefully terminate Gateway, Web UI, and all running domain runtimes and proxies:
```bash
./stop.sh
```

---

## 3. Supported Wallets & LocalNet Connection

### 1. KMD Dev Wallet
Algorand LocalNet includes an unencrypted default wallet pre-funded with 1,000 ALGO.
- **KMD URL**: `http://localhost:4002`
- **KMD Token**: `aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` (64 `a`s)
- **Wallet Name**: `unencrypted-default-wallet`
- Ideal for automated tests, faucet dispensing, and continuous integration.

### 2. Lute Wallet (Browser Extension / Web)
To connect the Lute browser wallet to LocalNet:
1. Open Lute settings and add a **Custom Network**:
   - **Network Name**: `Algorand LocalNet`
   - **Algod URL**: `http://localhost:4001`
   - **Algod Header / Token**: `aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa`
   - **Indexer URL**: `http://localhost:8980`
   - **Genesis ID**: `dockernet-v1`
2. Import an account using a mnemonic from `chain/accounts.json` (e.g. `client1` or `client2`).

### 3. Local Mnemonic Signer (Dev Only)
In local development and Vitest/Pytest suites, signers read credentials directly from `chain/accounts.json`. Mnemonics are strictly guarded and never exposed via public API endpoints.

---

## 4. How Payments Work (x402 Protocol)

1. **Client Dispatches Tool Call**: Client sends JSON-RPC tool execution request to `/api/listings/{id}/call`.
2. **HTTP 402 PAYMENT-REQUIRED**: The vendor proxy inspects requirements. If unauthenticated, it returns HTTP 402 with base64 payload:
   - `asset`: "0" (ALGO) or ASA ID (e.g., mUSD ID `3456`).
   - `amount`: Tool price in base units (microAlgos or micro-mUSD).
   - `payTo`: Vendor's on-chain public address.
   - `feePayer`: Vendor's address designated to cover transaction fees.
3. **Atomic Group Construction (`x402-avm-js`)**:
   - Txn 0: Vendor fee-payer self-payment of 0 ALGO with pooled fee (`2 * minFee`).
   - Txn 1: User payment of `amount` to vendor `payTo` with flat fee `0`.
   - The user wallet signs Txn 1 only.
4. **Retry with `PAYMENT-SIGNATURE`**: Client retries request with the signed group encoded in the HTTP header.
5. **Validation & Execution**: Vendor verifies signatures, validates simulated execution, and executes the MCP tool.
6. **Settle-on-Success**: Upon successful tool completion, the transaction group is broadcast to Algorand LocalNet and confirmed with instant finality.

---

## 5. Test Commands

Every command listed below has been executed and verified in this environment:

### Gateway Test Suite (Pytest)
```bash
# Offline unit tests
pytest gateway/tests/test_offline.py gateway/tests/test_security.py -v

# Full live test suite against LocalNet
LOCALNET=1 pytest gateway/tests -v
```

### Frontend Web Tests (Vitest)
```bash
cd web && npm test
```

### Chain Bootstrapping & Topology Tests
```bash
# Listing generation, vendor funding, asset opt-in, and marketplace consistency
LOCALNET=1 pytest chain/tests -v
```

### Market Activity Simulator
```bash
# Dry run deterministic call planning
python chain/simulate_market.py --dry-run

# Execute live simulated activity (5 buyers, 20 calls across tts, sandbox_mcp, latex_mcp, invoice_mcp)
python chain/simulate_market.py --buyers 5 --calls 20
```

### End-to-End Browser Playwright Tests (`marketplace/e2e`)
*Requires marketplace services running via `start.sh`*:
```bash
cd e2e && npx playwright test
```

---

## 6. Troubleshooting & Operational Guide

### Port Conflicts
Each domain occupies specific ports defined in `servers/topology.json`:
- Runtime servers: `8050`, `8059`, `8064`, `8070`, `8075`, `8081`, `8087`, `8091`, `8096`, `8099`, `8105`, `8111`, `8114`, `8119`, `8125`, `10000`.
- Gateway API: `8800`.
- Web UI: `5173`.
If a port is in use:
```bash
./status.sh
./stop.sh
```

### LocalNet Docker Network Recovery After Reboot
On system reboot, Docker containers (`algokit_algod`, `algokit_indexer`) may detach from their internal Docker bridge network (`algorand-localnet`). If Algod is unreachable:
```bash
# Reconnect containers to the localnet bridge
docker network connect algorand-localnet algokit_algod 2>/dev/null || true
docker network connect algorand-localnet algokit_indexer 2>/dev/null || true

# Test connectivity
curl -s http://localhost:4001/health
curl -s http://localhost:8980/health
```

### Stale KMD PID
If KMD fails to start or refuses port 4002 due to an unclean shutdown:
```bash
docker exec -it algokit_algod rm -f /opt/algorand/node/kmd-v0.5/data/kmd.pid 2>/dev/null || true
docker restart algokit_algod
```
