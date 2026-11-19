#!/usr/bin/env bash
# domainctl.sh up|down|status <domain>
# Starts/stops ONE domain (runtime + all proxies) using that domain's own venv and the ports in topology.json.
# Every process runs in its own session; PIDs go to tests/run/<domain>.pids so "down" only kills what "up" started.
set -uo pipefail
SERVERS="$(cd "$(dirname "$0")/.." && pwd)"
CMD="${1:?up|down|status}"; D="${2:?domain}"
DIR="$SERVERS/$D"; PY="$DIR/venv/bin/python"
RUN="$SERVERS/tests/run"; LOGS="$SERVERS/tests/logs"; mkdir -p "$RUN" "$LOGS"
PIDS="$RUN/$D.pids"
read -r RPORT PPORTS < <(python3 -c "
import json,sys; t=json.load(open('$SERVERS/topology.json'))['$D']
print(t['runtime_port'], ','.join(map(str,t['proxy_ports'])))")

port_open() { (exec 3<>/dev/tcp/127.0.0.1/"$1") 2>/dev/null && exec 3>&-; }
wait_port() { local p=$1 t=$2; for _ in $(seq 1 "$t"); do port_open "$p" && return 0; sleep 1; done; return 1; }

down() {
  [ -f "$PIDS" ] || { echo "$D: not running (no pid file)"; return 0; }
  while read -r pid; do kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null; done < "$PIDS"
  sleep 2
  while read -r pid; do kill -KILL -- "-$pid" 2>/dev/null; done < "$PIDS"
  rm -f "$PIDS"; echo "$D: stopped"
}

up() {
  [ -x "$PY" ] || { echo "$D: missing venv python $PY"; exit 2; }
  [ -f "$PIDS" ] && down
  for p in $RPORT ${PPORTS//,/ }; do port_open "$p" && { echo "$D: port $p already in use - refusing"; exit 3; }; done
  cd "$DIR" || exit 2
  setsid "$PY" runtime_server.py > "$LOGS/${D}_runtime.log" 2>&1 & echo $! >> "$PIDS"
  if ! wait_port "$RPORT" "${RUNTIME_WAIT:-180}"; then
    echo "$D: runtime did not open port $RPORT - last log lines:"; tail -n 25 "$LOGS/${D}_runtime.log"; down; exit 4; fi
  i=1
  for p in ${PPORTS//,/ }; do
    setsid "$PY" "mcp_server_$i.py" > "$LOGS/${D}_mcp$i.log" 2>&1 & echo $! >> "$PIDS"; i=$((i+1)); done
  i=1; ok=1
  for p in ${PPORTS//,/ }; do
    if ! wait_port "$p" 60; then echo "$D: proxy $i did not open port $p:"; tail -n 15 "$LOGS/${D}_mcp$i.log"; ok=0; fi; i=$((i+1)); done
  [ $ok = 1 ] && echo "$D: UP runtime=$RPORT proxies=$PPORTS" || { down; exit 5; }
}

status() {
  for p in $RPORT ${PPORTS//,/ }; do port_open "$p" && echo "$p open" || echo "$p closed"; done
}

case "$CMD" in up) up;; down) down;; status) status;; *) echo "usage: $0 up|down|status <domain>"; exit 1;; esac
