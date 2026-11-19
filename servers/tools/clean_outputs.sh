#!/usr/bin/env bash
set -uo pipefail

SERVERS="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

DAYS=7
DRY_RUN=0

while [ $# -gt 0 ]; do
  case "$1" in
    --days)
      if [ -n "${2:-}" ] && [[ "$2" =~ ^[0-9]+$ ]]; then
        DAYS="$2"
        shift 2
      else
        echo "Error: --days requires an integer argument." >&2
        exit 1
      fi
      ;;
    --days=*)
      DAYS="${1#*=}"
      if ! [[ "$DAYS" =~ ^[0-9]+$ ]]; then
        echo "Error: --days requires an integer argument." >&2
        exit 1
      fi
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      echo "Usage: $0 [--days N] [--dry-run]"
      echo "  --days N   Delete files older than N days (default: 7)"
      echo "  --dry-run  Show what would be deleted without actually deleting"
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      echo "Usage: $0 [--days N] [--dry-run]" >&2
      exit 1
      ;;
  esac
done

TARGET_DIRS=()
for d in "$SERVERS"/*/outputs; do
  if [ -d "$d" ] && [ "$d" != "$SERVERS/tests/outputs" ]; then
    TARGET_DIRS+=("$d")
  fi
done
if [ -d "$SERVERS/tests/outputs/probe" ]; then
  TARGET_DIRS+=("$SERVERS/tests/outputs/probe")
fi

echo "========================================================================"
echo "Cleaning server output directories (older than $DAYS days)"
if [ "$DRY_RUN" -eq 1 ]; then
  echo "MODE: DRY-RUN (no files will be deleted)"
else
  echo "MODE: LIVE (files will be deleted)"
fi
echo "Target directories:"
for t in "${TARGET_DIRS[@]}"; do
  echo "  - $t"
done
echo "========================================================================"

TOTAL_COUNT=0
TOTAL_BYTES=0

for target in "${TARGET_DIRS[@]}"; do
  [ -d "$target" ] || continue

  # Find all files older than DAYS
  while IFS= read -r -d '' file; do
    [ -f "$file" ] || continue
    size=$(stat -c%s "$file" 2>/dev/null || echo 0)
    TOTAL_COUNT=$((TOTAL_COUNT + 1))
    TOTAL_BYTES=$((TOTAL_BYTES + size))

    if [ "$DRY_RUN" -eq 1 ]; then
      echo "[DRY-RUN] Would remove: $file ($size bytes)"
    else
      echo "Removing: $file ($size bytes)"
      rm -f "$file"
    fi
  done < <(find "$target" -mindepth 1 -type f -mtime +"$DAYS" -print0 2>/dev/null)

  # In live mode, clean up empty subdirectories if any were left
  if [ "$DRY_RUN" -eq 0 ]; then
    find "$target" -mindepth 1 -depth -type d -empty -delete 2>/dev/null || true
  fi
done

HUMAN_SIZE=$(numfmt --to=iec-i --suffix=B "$TOTAL_BYTES" 2>/dev/null || echo "$TOTAL_BYTES bytes")

echo "========================================================================"
if [ "$DRY_RUN" -eq 1 ]; then
  echo "DRY-RUN SUMMARY: Would remove $TOTAL_COUNT files (~$HUMAN_SIZE)"
else
  echo "CLEANUP SUMMARY: Removed $TOTAL_COUNT files (~$HUMAN_SIZE)"
fi
echo "========================================================================"
