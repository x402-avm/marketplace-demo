#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ALGO_ROOT="$(cd "$DIR/../.." && pwd)"

echo "=== [e2e] Preparing environment ==="

GATEWAY_PID=""

cleanup() {
  echo "=== [e2e] Cleanup on exit ==="
  echo "Stopping tts domain..."
  "$ALGO_ROOT/servers/tools/domainctl.sh" down tts 2>/dev/null || true
  echo "Stopping sandbox_mcp domain..."
  "$ALGO_ROOT/servers/tools/domainctl.sh" down sandbox_mcp 2>/dev/null || true
  if [ -n "$GATEWAY_PID" ]; then
    echo "Stopping gateway (PID $GATEWAY_PID)..."
    kill "$GATEWAY_PID" 2>/dev/null || true
    wait "$GATEWAY_PID" 2>/dev/null || true
  fi
  echo "=== [e2e] Cleanup complete ==="
}
trap cleanup EXIT

# Check domainctl.sh status before starting tts or sandbox_mcp and wait if another worker has them up
check_and_wait() {
  local domain=$1
  while true; do
    local open_ports
    open_ports=$("$ALGO_ROOT/servers/tools/domainctl.sh" status "$domain" | grep -c "open" || true)
    if [ "$open_ports" -eq 0 ]; then
      break
    fi
    echo "Domain $domain has $open_ports open ports (in use by another worker). Waiting 10s..."
    sleep 10
  done
}

check_and_wait tts
check_and_wait sandbox_mcp

# 1. Start gateway
echo "Starting gateway backend..."
"$ALGO_ROOT/marketplace/gateway/run.sh" &
GATEWAY_PID=$!

echo "Waiting for gateway at http://127.0.0.1:8800/api/health..."
READY=0
for i in $(seq 1 30); do
  if curl -sf http://127.0.0.1:8800/api/health | grep -q '"ok":true'; then
    READY=1
    echo "Gateway is ready!"
    break
  fi
  sleep 1
done

if [ "$READY" -ne 1 ]; then
  echo "ERROR: Gateway failed to start within 30 seconds"
  exit 1
fi

# 2. Start PAYMENTS=on proxies for tts and sandbox_mcp
export PAYMENTS=on
echo "Starting PAYMENTS=on proxies for tts..."
"$ALGO_ROOT/servers/tools/domainctl.sh" up tts

echo "Starting PAYMENTS=on proxies for sandbox_mcp..."
"$ALGO_ROOT/servers/tools/domainctl.sh" up sandbox_mcp

# 3. Run Playwright test suite
echo "=== [e2e] Running Playwright test suite ==="
cd "$DIR"
npx playwright test "$@"
