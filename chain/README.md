# Algorand LocalNet Tooling

## What this is
This package provides tooling to interact with a local Algorand blockchain environment powered by **AlgoKit LocalNet**:
- **algod** (`http://localhost:4001`): Block production, account queries, and transaction submission.
- **kmd** (`http://localhost:4002`): Key Management Daemon managing pre-funded development wallets.
- **indexer** (`http://localhost:8980`): Historical block and transaction search.
- **Pure Proof-of-Stake (PoS)**: Algorand uses pure proof-of-stake with zero mining or proof-of-work. In LocalNet dev mode, a new block is produced immediately whenever a transaction group is submitted.
- **Cryptographic Hash Chain**: Blocks form a tamper-evident chain where each block header contains the hash of the preceding block (`prev`).

## Prerequisites
- **Docker**: Container engine running the LocalNet sandbox.
- **AlgoKit CLI**: Install via `uv tool install algokit` (executable at `~/.local/bin/algokit`).
- **Python 3.12+**: Python environment with `py-algorand-sdk` (`.venv/bin/python`).

## Start / Stop
Manage the local blockchain daemon using the AlgoKit CLI:
- Start services: `algokit localnet start`
- Check health: `algokit localnet status`
- Stop services: `algokit localnet stop`
- Reset network: `algokit localnet reset` (wipes the chain state and restarts from round 0; rerun `bootstrap.py` afterwards)

## Bootstrap
Run `python bootstrap.py` to initialize development accounts and tokens:
- **Idempotent**: Reuses existing configuration if the network genesis hash matches `accounts.json`.
- **Roles Created**:
  - `server`: Payment recipient and manager of subscriptions.
  - `client1`: Consumer account.
  - `client2`: Consumer account.
- **Auto-Funding**: Each role is topped up from the KMD dispenser to `1,000 ALGO` (`1,000,000,000 microAlgos`).
- **Subscription ASA**: Creates the `AI-SUB` asset (`unit_name: PASS`, `total: 1,000,000`) owned by `server`.
- **Opt-In**: Opts `client1` and `client2` into the subscription asset so they can receive passes.
- **Credentials**: Saved to `accounts.json` with restricted permissions (`chmod 600`).
> [!CAUTION]
> All keys in `accounts.json` and KMD are development keys for LocalNet only. Never use them on MainNet or TestNet.

## Explorer Commands

Use `explorer.py` to inspect blocks, wallets, and transactions:

### 1. `status`
Displays overall network status, genesis hash, last round, time elapsed since the last block, and wallet count.
```bash
$ python explorer.py status
Network: algorand:qNF74lmmiHUCf7s3oewhYsMzOCOEptuJ9ytCk5gBPGI=
Genesis Hash: qNF74lmmiHUCf7s3oewhYsMzOCOEptuJ9ytCk5gBPGI=
Last Round: 17
Time Since Last Block: 3.6s
KMD Wallets: 1
```

### 2. `wallets`
Lists KMD dispenser addresses and role accounts from `accounts.json` with balances and assets.
```bash
$ python explorer.py wallets
=== KMD Wallets ===
Wallet: unencrypted-default-wallet (ID: 3739a64ebf5c50895b884ed6e1696683)
  Address: KJOMA6RFFAJ46EOKEM6IDWOY3FRIB65HHQ7DB5QTHD4B6XKK7WG37WVMFU | Balance: 3999995999996000 microAlgos (3999995999.996000 ALGO)
  Address: OYBFY63VYXOESNN4FEHBKET6S5WGKYWWAH5TXUUDOF7TOUIK4BXXBMTW5Q | Balance: 3999996999997000 microAlgos (3999996999.997000 ALGO)
  Address: SAH5DPDNPFLR5SQFNQQ5A5SQ5VJC6QEBGJ54DFNEFY3URREINZGXKA7Y7M | Balance: 2000000000000000 microAlgos (2000000000.000000 ALGO)

=== Roles (from accounts.json) ===
Role: server | Address: SPDMDX4SBNY35L2GZB7RBKTPRT76NUVWA2GNXEQDTPPNKUOYJIK5ERFAW4 | Balance: 1001749000 microAlgos (1001.749000 ALGO) | Assets: [{'amount': 1000000, 'asset-id': 1010, 'is-frozen': False}]
Role: client1 | Address: I7UIALCHJU5562XCBX5XS7YZXKW5L4KA3EXUGLOFCVXSLC7PT2ZMUZEYJQ | Balance: 998998000 microAlgos (998.998000 ALGO) | Assets: [{'amount': 0, 'asset-id': 1010, 'is-frozen': False}]
Role: client2 | Address: ZZ7WSWCX2HYEFEK6VIBDEP7OTGIBFTJKWMJPGJASSKRIFDQUSXRL5VJCJA | Balance: 999247000 microAlgos (999.247000 ALGO) | Assets: [{'amount': 0, 'asset-id': 1010, 'is-frozen': False}]
```

### 3. `blocks [-n N]`
Lists the newest N block headers with normalized hashes (stripped of `blk-`).
```bash
$ python explorer.py blocks -n 3
Round 17   | Hash: PYWDSUF2UKHZCDBQGCONZEKXNRBJDDOH63ZM2AGF3MJYZCPIPIBQ | Prev: S62X67W2LZGFVZ7S5PP3M5VOKCFNAXRKSXYC6UMDM6YQO327Y5FQ | TS: 2026-11-16T22:47:55+00:00 | Txns: 1 | Proposer: -
Round 16   | Hash: S62X67W2LZGFVZ7S5PP3M5VOKCFNAXRKSXYC6UMDM6YQO327Y5FQ | Prev: 547VGL32VOGVXL4MECRMZ5UJOOKORZ5YMTWURGHNK522VPRMICMQ | TS: 2026-11-16T22:47:30+00:00 | Txns: 1 | Proposer: -
Round 15   | Hash: 547VGL32VOGVXL4MECRMZ5UJOOKORZ5YMTWURGHNK522VPRMICMQ | Prev: PTAESMHPQY2PKYRITXU333XSBQXQ4LRXFACL5LFLNVVHXBF7ZHBQ | TS: 2026-11-16T22:47:05+00:00 | Txns: 1 | Proposer: -
```

### 4. `block <round>`
Shows detailed header and transaction information for a specific block round.
```bash
$ python explorer.py block 17
Round: 17
Block Hash: PYWDSUF2UKHZCDBQGCONZEKXNRBJDDOH63ZM2AGF3MJYZCPIPIBQ
Prev Hash: S62X67W2LZGFVZ7S5PP3M5VOKCFNAXRKSXYC6UMDM6YQO327Y5FQ
Timestamp: 2026-11-16T22:47:55+00:00
Txns Count: 1
Proposer: -
Transactions:
  [0] Type: pay | Sender: ZZ7WSWCX2HYEFEK6VIBDEP7OTGIBFTJKWMJPGJASSKRIFDQUSXRL5VJCJA | Receiver: SPDMDX4SBNY35L2GZB7RBKTPRT76NUVWA2GNXEQDTPPNKUOYJIK5ERFAW4 | Amount: 250000
```

### 5. `verify [--from R0] [--to R1]`
Traverses the blockchain backward checking that block `r`'s previous hash matches block `r-1`'s block hash.
```bash
$ python explorer.py verify
OK hash-chain intact for rounds 0..17
```

### 6. `stats [-n N]`
Calculates transaction velocity, block interval, and transaction type breakdown over the last N rounds.
```bash
$ python explorer.py stats -n 30
First Round: 0
Last Round: 17
Number of Blocks: 18
Total Transactions: 17
Txns per Block (avg): 0.94
Average Seconds Between Blocks: 19.6s
Transactions by Type:
  acfg: 2
  axfer: 3
  pay: 12
Consensus: Algorand Pure Proof-of-Stake (no mining). LocalNet dev mode creates one block per transaction group.
```

### 7. `txns <role-or-address> [-n N]`
Queries Indexer for the most recent transactions associated with a role or Algorand address.
```bash
$ python explorer.py txns client2 -n 3
TxID: E5P3SWYJ3ZNPCR2D6Y4T6RKSHFJCWWREPQ5AF2EHOA5AUAMECKYQ | Round: 17 | Type: pay | Sender: ZZ7WSWCX2HYEFEK6VIBDEP7OTGIBFTJKWMJPGJASSKRIFDQUSXRL5VJCJA | Receiver: SPDMDX4SBNY35L2GZB7RBKTPRT76NUVWA2GNXEQDTPPNKUOYJIK5ERFAW4 | Amount: 250000 | Note: T14 check
TxID: 5DU4JPEMFON7HV4A5SOWLKZV52FRFFEWRE2M3EZXTOEG5GQXMF5A | Round: 16 | Type: pay | Sender: ZZ7WSWCX2HYEFEK6VIBDEP7OTGIBFTJKWMJPGJASSKRIFDQUSXRL5VJCJA | Receiver: SPDMDX4SBNY35L2GZB7RBKTPRT76NUVWA2GNXEQDTPPNKUOYJIK5ERFAW4 | Amount: 500000 | Note: -
TxID: 6EUW4TR6DBQJXBHFSDWDGEAJ2EKZMO7UPCTRF6OR4S7IYGIIKMMQ | Round: 14 | Type: pay | Sender: ZZ7WSWCX2HYEFEK6VIBDEP7OTGIBFTJKWMJPGJASSKRIFDQUSXRL5VJCJA | Receiver: SPDMDX4SBNY35L2GZB7RBKTPRT76NUVWA2GNXEQDTPPNKUOYJIK5ERFAW4 | Amount: 500000 | Note: -
```

### 8. `send <from-role> <to-role-or-address> <microalgos> [--note TEXT]`
Signs and sends a payment transaction on LocalNet and waits for round confirmation.
```bash
$ python explorer.py send client2 server 250000 --note "T14 check"
Transaction sent: txid=E5P3SWYJ3ZNPCR2D6Y4T6RKSHFJCWWREPQ5AF2EHOA5AUAMECKYQ confirmed_round=17
```

### 9. `watch`
Monitors the blockchain in real-time, printing new blocks and transaction counts as they are committed.
```bash
$ python explorer.py watch
Watching for new blocks (latest round: 17)... Press Ctrl-C to stop.
Round 18: hash W5E2U..., txns: 1
```

---

## Payments on chain

The Algorand LocalNet environment powers the `x402` payment layer across the 16-domain MCP fleet:

### Atomic Transaction Group Structure
When an MCP client pays for a tool call, the transaction settles on-chain as a **2-transaction atomic group**:
1. **Txn 0 (Server Fee Payer)**: Sender `server`, Receiver `server`, Amount `0`, Fee `2,000 microalgos` (`2 x 1,000` min fee). Note: `x402-fee-payer-<nonce>`.
2. **Txn 1 (Client Payment)**: Sender `payer`, Receiver `server`, Amount `<price>`, Fee `0`. Note: `x402-payment-<nonce>`.

Because the server acts as fee payer for both transactions in the group, it incurs `2,000 microalgos` in network fees.

### Pricing, Fee Floor, and Economics
- **Pricing**: Defined in `servers/pricing.json` (minimum 3,000 microalgos; default 3,000).
- **Fee Floor**: The SDK's `PaymentGate` enforces a strict fee floor (`fee_cost = 2,000 microalgos`). Any price `<= 2,000` microalgos loses money and is rejected unless `allow_loss=True`.
- **Real Execution Examples**:
  - `latex_mcp` / `ocr_mcp` (price 6,000): client pays 6,000, server pays 2,000 fee -> `paid=6000 fee=2000 net=4000`.
  - `paper_mcp` / `domain_mcp` (price 3,000): client pays 3,000, server pays 2,000 fee -> `paid=3000 fee=2000 net=1000`.

### Identity, Subscriptions & Bulk Discounts
- **Identity Proofs**: Off-chain Ed25519-signed headers (`x-sender-address`, `x-sender-timestamp`, `x-sender-signature`) authenticate the caller within a 120s timestamp skew window.
- **Subscriptions**: Holding the `AI-SUB` ASA (created during `bootstrap.py`) transferred within 30 days provides free tool calls.
- **Bulk Discounts**: Callers with > 1 ALGO (`1,000,000 microalgos`) spent in the trailing 30 days receive 50% discount (clamped to `2,001 microalgos` by the fee floor).

### Replay Protection & Settlement Policy
- **Charge Only on Success**: `PaymentGate` hooks into MCP response processing (`gate.py:80-110`). If a tool execution fails (`isError=True` or `ToolError`), payment settlement is aborted, the signed transaction is discarded, and no transaction is submitted to the chain. Callers are never charged for failed tool calls.
- **Replay Protection**: Replayed payment payloads return HTTP 402 and are rejected before chain submission. Production MCP servers share a SQLite `ReplayStore` with WAL (`servers/tests/run/replay_<domain>.sqlite`), preventing replay attacks across multiple thin proxy workers.

### Verifying Payments on Chain
Inspect confirmed payment transactions and verify blockchain state:
```bash
# Query recent payment transactions to the server
python explorer.py txns server -n 10

# Verify complete blockchain hash-chain integrity
python explorer.py verify
```


---

## Marketplace Actors

### Roles Table
| Role (`accounts.json` key) | Display Name | Purpose | Initial Funding | Accepted Asset | Multiplier |
|---|---|---|---|---|---|
| `server` | Marketplace Treasury | Issuer of `AI-SUB` and `mUSD`, sells subscriptions, funds faucet | 1,000 ALGO | ALGO | 1.0 |
| `client1` | Test Buyer 1 | Consumer / buyer account | 1,000 ALGO + 1,000 mUSD | ALGO / mUSD | - |
| `client2` | Test Buyer 2 | Consumer / buyer account | 1,000 ALGO + 1,000 mUSD | ALGO / mUSD | - |
| `vendorA` | Nova Labs | Service vendor, receives payments, acts as x402 fee payer | 100 ALGO | ALGO | 1.0 |
| `vendorB` | Blue Fern AI | Service vendor, receives payments in mUSD | 100 ALGO | mUSD | 0.8 |
| `vendorC` | Quarry Compute | Service vendor, receives payments, acts as x402 fee payer | 100 ALGO | ALGO | 1.25 |
| `vendorD` | Lumen Works | Service vendor, receives payments, acts as x402 fee payer | 100 ALGO | ALGO | 1.5 |

### Assets
1. **ALGO** (`asset_id: 0`): Native blockchain currency (6 decimals, 1 ALGO = 1,000,000 microAlgos).
2. **mUSD** (Marketplace USD ASA, `decimals: 6`, `total: 10^15`):
   - Created and reserved by `server` (Treasury).
   - 1 mUSD corresponds to 1 ALGO in base units (6 decimals).
   - Accepted by `vendorB` for all its service listings.
   - `client1` and `client2` receive an initial balance of 1,000 mUSD (`1,000,000,000` base units).
   - All vendors and clients opt into mUSD during bootstrapping.
   - Lookup current mUSD Asset ID: `python -c "import json; print(json.load(open('chain/accounts.json'))['musd_asset_id'])"`
3. **AI-SUB** (Subscription ASA, `decimals: 0`, `total: 1,000,000`):
   - Created and managed by `server` (Treasury).
   - Grants 30-day unlimited subscription access across all MCP listings.
   - All vendors and clients opt into AI-SUB during bootstrapping.

### Marketplace Listings & Regeneration
The service fleet topology (16 domains, 64 proxy endpoints) maps deterministically to vendors and pricing:
- Proxy index $i$ of domain $D$ maps to vendor `["vendorA", "vendorB", "vendorC", "vendorD"][(i - 1) % 4]`.
- Listing prices are computed as `max(round(base_price * multiplier), minimum_price)` where minimum price defaults to 3,000.
- `vendorB` listings accept `mUSD`; all others accept `ALGO`.
- To regenerate `servers/marketplace.json`:
  ```bash
  python chain/gen_listings.py
  ```
- To test chain actors and marketplace configuration:
  ```bash
  LOCALNET=1 python -m pytest chain/tests -q
  ```


---

## Market Simulator

The activity simulator (`simulate_market.py`) exercises the end-to-end multi-vendor marketplace on LocalNet:
- **Buyer Generation**: Generates $N$ ephemeral buyer accounts in memory (never written to disk).
- **Auto-Provisioning**: Automatically funds each buyer with 20 ALGO from the KMD dispenser, opts each into `mUSD`, and transfers 200 mUSD from the Treasury (`server`).
- **Activity Generation**: Dispatches $M$ paid MCP calls across active listings of the selected domains (`tts`, `sandbox_mcp`, `latex_mcp`, `invoice_mcp` by default). Each call resolves positive test arguments from `servers/tools/test_matrix.json` and pays via `ai_economy_sdk.client.paid_mcp_session`.
- **Payment Settlement**: Automatically settles in the listing's native currency (ALGO or mUSD). The listing's vendor acts as fee payer (`2,000 microAlgos` network fee per call), while the buyer pays the listing's tool price.
- **On-Chain Balance Reconciliation**: Tracks exact on-chain balance deltas for all 4 vendors (`vendorA..D`) and reconciles them against transaction records minus network fees paid.

### Usage
```bash
# Dry-run plan (prints projected calls and vendor totals without submitting transactions):
python simulate_market.py --buyers 5 --calls 20 --seed 1 --dry-run

# Live execution against running MCP servers:
python simulate_market.py --buyers 5 --calls 20 --seed 1
```
