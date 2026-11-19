#!/usr/bin/env bash
# marketplace/status.sh: Check status of LocalNet, MCP service domains, Gateway, and Web UI.
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

port_open() {
  (exec 3<>/dev/tcp/127.0.0.1/"$1") 2>/dev/null && exec 3>&-
}

echo "================================================================================"
echo " MARKETPLACE SYSTEM STATUS"
echo "================================================================================"

# 1. LocalNet Checks
echo "--- [1] LocalNet Infrastructure ---"
ALGOD_STATUS="DOWN"
ALGOD_ROUND="unknown"
ALGO_TOKEN="$(printf 'a%.0s' {1..64})"
if port_open 4001; then
  ALGOD_RESP=$(curl -s -f -H "X-Algo-API-Token: $ALGO_TOKEN" http://localhost:4001/v2/status 2>/dev/null || true)
  if [ -n "$ALGOD_RESP" ]; then
    ALGOD_ROUND=$(echo "$ALGOD_RESP" | grep -o '"last-round":[0-9]*' | cut -d: -f2 || echo "ok")
    ALGOD_STATUS="UP (round: $ALGOD_ROUND)"
  elif curl -s -f http://localhost:4001/health >/dev/null 2>&1; then
    ALGOD_STATUS="UP"
  fi
fi

INDEXER_STATUS="DOWN"
if port_open 8980; then
  if curl -s -f http://localhost:8980/health >/dev/null 2>&1; then
    INDEXER_STATUS="UP"
  else
    INDEXER_STATUS="PORT OPEN"
  fi
fi

KMD_STATUS="DOWN"
KMD_TOKEN="$(printf 'a%.0s' {1..64})"
if port_open 4002; then
  if curl -s -f -H "X-KMD-API-Token: $KMD_TOKEN" http://localhost:4002/v1/wallets >/dev/null 2>&1; then
    KMD_STATUS="UP"
  else
    KMD_STATUS="PORT OPEN"
  fi
fi

printf "  %-12s : %-30s (port 4001)\n" "Algod" "$ALGOD_STATUS"
printf "  %-12s : %-30s (port 8980)\n" "Indexer" "$INDEXER_STATUS"
printf "  %-12s : %-30s (port 4002)\n" "KMD" "$KMD_STATUS"
echo ""

# 2. Service Domains
echo "--- [2] Paid Service Domains (16 MCP Domains) ---"
printf "%-18s | %-10s | %-14s | %-24s\n" "Domain" "Status" "Runtime Port" "Proxy Ports"
echo "--------------------------------------------------------------------------------"

DOMAINS_UP=0
DOMAINS_TOTAL=0

if [ -f "$SERVERS_DIR/topology.json" ]; then
  # Parse domain list and ports using python
  while IFS='|' read -r d rport pports; do
    DOMAINS_TOTAL=$((DOMAINS_TOTAL + 1))
    
    r_open=0
    port_open "$rport" && r_open=1
    
    p_total=0
    p_open=0
    for p in ${pports//,/ }; do
      p_total=$((p_total + 1))
      port_open "$p" && p_open=$((p_open + 1))
    done
    
    status="DOWN"
    if [ "$r_open" -eq 1 ] && [ "$p_open" -eq "$p_total" ]; then
      status="UP"
      DOMAINS_UP=$((DOMAINS_UP + 1))
    elif [ "$r_open" -eq 1 ] || [ "$p_open" -gt 0 ]; then
      status="PARTIAL ($p_open/$p_total)"
    fi
    
    printf "%-18s | %-10s | %-14s | %-24s\n" "$d" "$status" "$rport ($([ $r_open -eq 1 ] && echo 'open' || echo 'closed'))" "$pports ($p_open/$p_total open)"
  done < <("$VENV_PY" -c "
import json
with open('$SERVERS_DIR/topology.json') as f:
    topo = json.load(f)
for d, cfg in topo.items():
    print(f\"{d}|{cfg['runtime_port']}|{','.join(map(str, cfg['proxy_ports']))}\")
")
fi
echo "Summary: $DOMAINS_UP / $DOMAINS_TOTAL domains fully UP"
echo ""

# 3. Gateway Status
echo "--- [3] Marketplace Gateway API ---"
GW_PID="none"
if [ -f "$RUN_DIR/gateway.pid" ]; then
  GW_PID="$(cat "$RUN_DIR/gateway.pid" 2>/dev/null || echo "none")"
fi

GW_STATUS="DOWN"
if port_open 8800; then
  GW_HEALTH=$(curl -s -f http://localhost:8800/api/health 2>/dev/null || true)
  if [ -n "$GW_HEALTH" ]; then
    GW_ROUND=$(echo "$GW_HEALTH" | grep -o '"round":[0-9]*' | cut -d: -f2 || echo "ok")
    GW_STATUS="UP (round: $GW_ROUND)"
  else
    GW_STATUS="PORT OPEN"
  fi
fi
printf "  %-12s : %-30s (pid: %s, port 8800)\n" "Gateway" "$GW_STATUS" "$GW_PID"
echo ""

# 4. Web UI Status
echo "--- [4] Marketplace Web Frontend ---"
WEB_PID="none"
if [ -f "$RUN_DIR/web.pid" ]; then
  WEB_PID="$(cat "$RUN_DIR/web.pid" 2>/dev/null || echo "none")"
fi

WEB_STATUS="DOWN"
if port_open 5173; then
  WEB_STATUS="UP"
fi
printf "  %-12s : %-30s (pid: %s, port 5173)\n" "Web UI" "$WEB_STATUS" "$WEB_PID"
echo "================================================================================"
