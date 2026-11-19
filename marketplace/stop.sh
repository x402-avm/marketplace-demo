#!/usr/bin/env bash
# marketplace/stop.sh: Stop Gateway, Web UI, and all running MCP service domains.
set -uo pipefail

MARKETPLACE_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$MARKETPLACE_DIR/.." && pwd)"
SERVERS_DIR="$ROOT_DIR/servers"
RUN_DIR="$MARKETPLACE_DIR/.run"

echo "================================================================================"
echo " STOPPING MARKETPLACE SERVICES"
echo "================================================================================"

# 1. Stop Web UI
if [ -f "$RUN_DIR/web.pid" ]; then
  WEB_PID="$(cat "$RUN_DIR/web.pid" 2>/dev/null || true)"
  if [ -n "$WEB_PID" ]; then
    echo "Stopping Web UI (pid $WEB_PID)..."
    kill -TERM -- "-$WEB_PID" 2>/dev/null || kill -TERM "$WEB_PID" 2>/dev/null || true
    sleep 1
    kill -KILL -- "-$WEB_PID" 2>/dev/null || true
  fi
  rm -f "$RUN_DIR/web.pid"
  echo "Web UI stopped."
else
  echo "Web UI: not running (no pidfile)."
fi

# 2. Stop Gateway
if [ -f "$RUN_DIR/gateway.pid" ]; then
  GW_PID="$(cat "$RUN_DIR/gateway.pid" 2>/dev/null || true)"
  if [ -n "$GW_PID" ]; then
    echo "Stopping Gateway (pid $GW_PID)..."
    kill -TERM -- "-$GW_PID" 2>/dev/null || kill -TERM "$GW_PID" 2>/dev/null || true
    sleep 1
    kill -KILL -- "-$GW_PID" 2>/dev/null || true
  fi
  rm -f "$RUN_DIR/gateway.pid"
  echo "Gateway stopped."
else
  echo "Gateway: not running (no pidfile)."
fi

# 3. Stop MCP Domains
echo "Checking running MCP service domains..."
STOPPED_DOMAINS=0
for pidfile in "$SERVERS_DIR"/tests/run/*.pids; do
  [ -f "$pidfile" ] || continue
  DOMAIN="$(basename "$pidfile" .pids)"
  echo "Stopping domain '$DOMAIN'..."
  "$SERVERS_DIR/tools/domainctl.sh" down "$DOMAIN" || true
  STOPPED_DOMAINS=$((STOPPED_DOMAINS + 1))
done

if [ "$STOPPED_DOMAINS" -eq 0 ]; then
  echo "No domain services were running."
else
  echo "Stopped $STOPPED_DOMAINS domain(s)."
fi

echo "================================================================================"
echo " Marketplace shutdown complete."
echo " Run '$MARKETPLACE_DIR/status.sh' to verify."
echo "================================================================================"
