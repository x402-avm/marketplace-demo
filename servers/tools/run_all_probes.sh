#!/usr/bin/env bash
set -uo pipefail

SERVERS="$(cd "$(dirname "$0")/.." && pwd)"
TOPOLOGY="$SERVERS/topology.json"
OUT_DIR="$SERVERS/tests/outputs/probe"
mkdir -p "$OUT_DIR"

DOMAINS=()
EXTRA_ARGS=()
parsing_extra=0

for arg in "$@"; do
  if [ "$arg" = "--" ]; then
    parsing_extra=1
    continue
  fi
  if [ $parsing_extra -eq 1 ]; then
    EXTRA_ARGS+=("$arg")
  else
    DOMAINS+=("$arg")
  fi
done

if [ ${#DOMAINS[@]} -eq 0 ]; then
  mapfile -t ALL_DOMAINS < <(python3 -c "import json; print('\n'.join(json.load(open('$TOPOLOGY')).keys()))")
  for d in "${ALL_DOMAINS[@]}"; do
    if [ "$d" != "image_gen" ]; then
      DOMAINS+=("$d")
    fi
  done
fi

declare -A SUMMARY_LINES
declare -A DOMAIN_STATUS
ALL_PASS=1

for d in "${DOMAINS[@]}"; do
  echo ""
  echo "=================================================="
  echo "Probing domain: $d"
  echo "=================================================="

  up_ok=0
  if [ "$d" = "image_gen" ]; then
    if FAST_TEST_MODE="${FAST_TEST_MODE:-0}" RUNTIME_WAIT="${RUNTIME_WAIT:-600}" "$SERVERS/tools/domainctl.sh" up "$d"; then
      up_ok=1
    fi
  else
    if "$SERVERS/tools/domainctl.sh" up "$d"; then
      up_ok=1
    fi
  fi

  if [ $up_ok -eq 1 ]; then
    py="$SERVERS/$d/venv/bin/python"
    txt_out="$OUT_DIR/$d.txt"
    json_out="$OUT_DIR/$d.json"

    if [ -x "$py" ]; then
      set +e
      "$py" "$SERVERS/tools/probe.py" "$d" --json "$json_out" "${EXTRA_ARGS[@]}" 2>&1 | tee "$txt_out"
      set -e
      sum_line=$(grep "^SUMMARY $d:" "$txt_out" | tail -n 1 || true)
      if [ -n "$sum_line" ]; then
        SUMMARY_LINES["$d"]="$sum_line"
        # Parse X/Y checks passed
        read -r passed total < <(echo "$sum_line" | sed -n 's/^SUMMARY [^:]*: *\([0-9]*\)\/\([0-9]*\) checks passed.*/\1 \2/p')
        if [ -n "$passed" ] && [ -n "$total" ] && [ "$passed" -eq "$total" ] && [ "$total" -gt 0 ]; then
          DOMAIN_STATUS["$d"]="PASS"
        else
          DOMAIN_STATUS["$d"]="FAIL"
          ALL_PASS=0
        fi
      else
        SUMMARY_LINES["$d"]="SUMMARY $d: No summary line produced"
        DOMAIN_STATUS["$d"]="FAIL"
        ALL_PASS=0
      fi
    else
      SUMMARY_LINES["$d"]="SUMMARY $d: Missing venv python $py"
      DOMAIN_STATUS["$d"]="FAIL"
      ALL_PASS=0
    fi

    "$SERVERS/tools/domainctl.sh" down "$d"
  else
    SUMMARY_LINES["$d"]="SUMMARY $d: Failed to start"
    DOMAIN_STATUS["$d"]="FAIL"
    ALL_PASS=0
    "$SERVERS/tools/domainctl.sh" down "$d" 2>/dev/null || true
  fi
done

# Write SUMMARY.md
SUMMARY_MD="$OUT_DIR/SUMMARY.md"
{
  echo "# MCP Probes Summary"
  echo ""
  echo "| Domain | Result | Status |"
  echo "| --- | --- | --- |"
  for d in "${DOMAINS[@]}"; do
    echo "| $d | ${SUMMARY_LINES[$d]} | ${DOMAIN_STATUS[$d]} |"
  done
} > "$SUMMARY_MD"

echo ""
echo "=================================================="
echo "Final Probe Summary"
echo "=================================================="
cat "$SUMMARY_MD"
echo ""

if [ $ALL_PASS -eq 1 ]; then
  echo "All domains passed."
  exit 0
else
  echo "One or more domains failed."
  exit 1
fi
