#!/usr/bin/env bash
set -uo pipefail

SERVERS="$(cd "$(dirname "$0")" && pwd)"
TOPOLOGY="$SERVERS/topology.json"

if [ $# -gt 0 ]; then
  DOMAINS=("$@")
else
  mapfile -t DOMAINS < <(python3 -c "import json; print('\n'.join(json.load(open('$TOPOLOGY')).keys()))")
fi

for d in "${DOMAINS[@]}"; do
  "$SERVERS/tools/domainctl.sh" down "$d"
done

echo "stop_all: completed"
