#!/usr/bin/env bash
# marketplace/start.sh: One-command startup for Algorand AI Service Marketplace.
# Usage: start.sh [--domains d1,d2,...] [--no-web] [--no-paid]
set -uo pipefail

MARKETPLACE_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$MARKETPLACE_DIR/.." && pwd)"
SERVERS_DIR="$ROOT_DIR/servers"
RUN_DIR="$MARKETPLACE_DIR/.run"
if [ -z "${VENV_PY:-}" ] || [ ! -x "$VENV_PY" ]; then
  if [ -x "$ROOT_DIR/.venv/bin/python" ]; then
    VENV_PY="$ROOT_DIR/.venv/bin/python"
  elif command -v python3 >/dev/null 2>&1; then
    VENV_PY="$(command -v python3)"
  elif command -v python >/dev/null 2>&1; then
    VENV_PY="$(command -v python)"
  fi
fi

mkdir -p "$RUN_DIR"

# Defaults
CUSTOM_DOMAINS=""
START_WEB=1
ENABLE_PAID=1

port_open() {
  (exec 3<>/dev/tcp/127.0.0.1/"$1") 2>/dev/null && exec 3>&-
}

wait_url() {
  local url="$1" timeout="${2:-30}"
  for _ in $(seq 1 "$timeout"); do
    if curl -s -f "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  return 1
}

# Parse arguments
while [ $# -gt 0 ]; do
  case "$1" in
    --domains)
      shift
      CUSTOM_DOMAINS="${1:-}"
      shift || true
      ;;
    --domains=*)
      CUSTOM_DOMAINS="${1#*=}"
      shift
      ;;
    --no-web)
      START_WEB=0
      shift
      ;;
    --no-paid)
      ENABLE_PAID=0
      shift
      ;;
    -h|--help)
      echo "Usage: $0 [--domains d1,d2,...] [--no-web] [--no-paid]"
      echo "  --domains  Comma-separated list of domains to start (default: all 16 domains)"
      echo "  --no-web   Do not start the Web frontend (Vite)"
      echo "  --no-paid  Disable paid mode (PAYMENTS=off)"
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      echo "Usage: $0 [--domains d1,d2,...] [--no-web] [--no-paid]"
      exit 1
      ;;
  esac
done

echo "================================================================================"
echo " STARTING ALGORAND AI SERVICE MARKETPLACE"
echo "================================================================================"

# -----------------------------------------------------------------------------
# 1. Check LocalNet
# -----------------------------------------------------------------------------
echo "[1/5] Verifying Algorand LocalNet status..."
KMD_TOKEN="$(printf 'a%.0s' {1..64})"
LOCALNET_OK=1

if ! curl -s -f http://localhost:4001/health >/dev/null 2>&1; then
  echo "  [FAIL] Algod not responding at http://localhost:4001/health"
  LOCALNET_OK=0
fi

if ! curl -s -f http://localhost:8980/health >/dev/null 2>&1; then
  echo "  [FAIL] Indexer not responding at http://localhost:8980/health"
  LOCALNET_OK=0
fi

if ! curl -s -f -H "X-KMD-API-Token: $KMD_TOKEN" http://localhost:4002/v1/wallets >/dev/null 2>&1; then
  echo "  [FAIL] KMD not responding at http://localhost:4002/v1/wallets"
  LOCALNET_OK=0
fi

if [ "$LOCALNET_OK" -ne 1 ]; then
  echo ""
  echo "LocalNet is down - run: algokit localnet start"
  exit 1
fi
echo "  [OK] Algod (:4001), Indexer (:8980), and KMD (:4002) are active."

# -----------------------------------------------------------------------------
# 2. Bootstrap & Generate Listings
# -----------------------------------------------------------------------------
echo "[2/5] Bootstrapping accounts, assets, and marketplace listings..."
"$VENV_PY" "$ROOT_DIR/chain/bootstrap.py"
"$VENV_PY" "$ROOT_DIR/chain/gen_listings.py"

# -----------------------------------------------------------------------------
# 3. Start MCP Service Domains
# -----------------------------------------------------------------------------
if [ "$ENABLE_PAID" -eq 1 ]; then
  export PAYMENTS=on
  echo "[3/5] Starting MCP service domains (PAYMENTS=on)..."
else
  export PAYMENTS=off
  echo "[3/5] Starting MCP service domains (PAYMENTS=off)..."
fi

if [ -n "$CUSTOM_DOMAINS" ]; then
  IFS=',' read -r -a DOMAINS_ARRAY <<< "$CUSTOM_DOMAINS"
else
  # Default all 16 domains from topology.json
  DOMAINS_STR="$("$VENV_PY" -c "
import json
with open('$SERVERS_DIR/topology.json') as f:
    topo = json.load(f)
print(' '.join(topo.keys()))
")"
  read -r -a DOMAINS_ARRAY <<< "$DOMAINS_STR"
fi

declare -A DOMAIN_RESULTS

for d in "${DOMAINS_ARRAY[@]}"; do
  [ -z "$d" ] && continue
  echo "  Starting domain '$d'..."
  if [ "$d" = "image_gen" ]; then
    RUNTIME_WAIT=600 "$SERVERS_DIR/tools/domainctl.sh" up "$d" || true
  else
    "$SERVERS_DIR/tools/domainctl.sh" up "$d" || true
  fi

  # Record status
  if [ -f "$SERVERS_DIR/tests/run/$d.pids" ]; then
    DOMAIN_RESULTS["$d"]="UP"
  else
    DOMAIN_RESULTS["$d"]="FAILED"
  fi
done

echo ""
echo "--- MCP Domain Startup Status ---"
printf "%-18s | %-10s\n" "Domain" "Status"
echo "------------------------------"
for d in "${DOMAINS_ARRAY[@]}"; do
  [ -z "$d" ] && continue
  printf "%-18s | %-10s\n" "$d" "${DOMAIN_RESULTS[$d]:-UNKNOWN}"
done
echo ""

# -----------------------------------------------------------------------------
# 4. Gateway
# -----------------------------------------------------------------------------
echo "[4/5] Starting Gateway API..."
if port_open 8800 && curl -s -f http://localhost:8800/api/health >/dev/null 2>&1; then
  echo "  Gateway is already running on port 8800."
else
  # Clean old pid file if stale
  rm -f "$RUN_DIR/gateway.pid"
  setsid "$MARKETPLACE_DIR/gateway/run.sh" > "$RUN_DIR/gateway.log" 2>&1 &
  echo $! > "$RUN_DIR/gateway.pid"

  echo "  Waiting for Gateway /api/health..."
  if wait_url "http://localhost:8800/api/health" 30; then
    echo "  [OK] Gateway UP at http://localhost:8800"
  else
    echo "  [WARN] Gateway did not respond within 30s. Check log: $RUN_DIR/gateway.log"
  fi
fi

# -----------------------------------------------------------------------------
# 5. Web UI
# -----------------------------------------------------------------------------
if [ "$START_WEB" -eq 1 ]; then
  echo "[5/5] Starting Marketplace Web Frontend..."
  if port_open 5173; then
    echo "  Web UI is already running on port 5173."
  else
    rm -f "$RUN_DIR/web.pid"
    (
      cd "$MARKETPLACE_DIR/web"
      setsid npm run dev -- --port 5173 --strictPort > "$RUN_DIR/web.log" 2>&1 &
      echo $! > "$RUN_DIR/web.pid"
    )

    echo "  Waiting for Web UI at http://localhost:5173..."
    if wait_url "http://localhost:5173" 30; then
      echo "  [OK] Web UI UP at http://localhost:5173"
    else
      echo "  [WARN] Web UI did not respond within 30s. Check log: $RUN_DIR/web.log"
    fi
  fi
else
  echo "[5/5] Skipping Web UI (--no-web specified)."
fi

echo ""
echo "================================================================================"
echo " MARKETPLACE READY"
echo "================================================================================"
echo "Service Endpoints:"
[ "$START_WEB" -eq 1 ] && echo "  - Web Frontend  : http://localhost:5173"
echo "  - Gateway API   : http://localhost:8800"
echo "  - Algod (Node)  : http://localhost:4001"
echo "  - Indexer       : http://localhost:8980"
echo "  - KMD Wallet    : http://localhost:4002"
echo ""
echo "Supported Wallets:"
echo "  1. KMD Dev Wallet : 'unencrypted-default-wallet' (LocalNet dispenser with 1000 ALGO)"
echo "  2. Lute Wallet    : Add Custom Network pointing at:"
echo "                      Algod: http://localhost:4001 (Token: $(printf 'a%.0s' {1..64}))"
echo "                      Indexer: http://localhost:8980"
echo "  3. Dev Mnemonic   : Use test accounts (client1, client2) from chain/accounts.json"
echo ""
echo "To check system health: ./status.sh (or marketplace/status.sh)"
echo "To stop all services  : ./stop.sh (or marketplace/stop.sh)"
echo "================================================================================"
