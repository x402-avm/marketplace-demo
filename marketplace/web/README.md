# Marketplace Web UI

Interactive React and TypeScript frontend for the Algorand AI Service Marketplace demonstration, built with Vite and powered by the [`x402-avm-js`](https://github.com/x402-avm/x402-avm-js) client library.

The web app allows users to:
- Browse 64 paid AI tool listings across 4 vendors.
- Connect local wallets (Lute extension, AlgoKit KMD dev wallet, or local dev mnemonics).
- Request testnet funds via the built-in LocalNet faucet (ALGO and mUSD).
- Execute paid MCP tool calls with automatic HTTP 402 negotiation, transaction signing, and settle-on-success verification.
- Purchase and manage vendor-scoped subscription passes.

## Development

The web interface connects to the FastAPI marketplace gateway running on `http://localhost:8800` (configured via `VITE_GATEWAY_URL` in `.env.local` or defaulting to `http://localhost:8800`).

### Install Dependencies

```bash
npm ci
```

### Start Development Server

Starts the Vite local development server on `http://localhost:5173`:

```bash
npm run dev
```

### Build for Production

Compiles TypeScript and creates optimized static assets in `dist/`:

```bash
npm run build
```

### Run Tests

Executes unit tests using Vitest:

```bash
npm test
```
