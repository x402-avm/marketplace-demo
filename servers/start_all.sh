#!/usr/bin/env bash
set -uo pipefail

SERVERS="$(cd "$(dirname "$0")" && pwd)"
TOPOLOGY="$SERVERS/topology.json"

if [ $# -gt 0 ]; then
  DOMAINS=("$@")
else
  mapfile -t DOMAINS < <(python3 -c "import json; print('\n'.join(json.load(open('$TOPOLOGY')).keys()))")
fi

declare -A RESULTS
FAILED_COUNT=0

for d in "${DOMAINS[@]}"; do
  echo ">>> Starting domain: $d"
  if [ "$d" = "image_gen" ]; then
    FAST_TEST_MODE="${FAST_TEST_MODE:-1}" RUNTIME_WAIT="${RUNTIME_WAIT:-600}" "$SERVERS/tools/domainctl.sh" up "$d"
    rc=$?
  else
    "$SERVERS/tools/domainctl.sh" up "$d"
    rc=$?
  fi

  if [ $rc -eq 0 ]; then
    RESULTS["$d"]="UP"
  else
    RESULTS["$d"]="FAILED"
    FAILED_COUNT=$((FAILED_COUNT + 1))
  fi
done

echo ""
echo "=== Domain Startup Summary ==="
printf "%-20s | %s\n" "Domain" "Status"
printf "%-20s-+-%s\n" "--------------------" "------"
for d in "${DOMAINS[@]}"; do
  printf "%-20s | %s\n" "$d" "${RESULTS[$d]}"
done

if [ $FAILED_COUNT -gt 0 ]; then
  echo ""
  echo "Error: $FAILED_COUNT domain(s) failed to start."
  exit 1
fi
