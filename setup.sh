#!/usr/bin/env bash
# setup.sh: One-command environment setup for the Algorand AI Service Marketplace Demo.
# Creates .venv, installs dependencies across all service domains, and builds the web app.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$ROOT_DIR/.venv"

echo "======================================================================"
echo " Algorand AI Service Marketplace — Environment Setup"
echo "======================================================================"

# 1. Check Python version (>= 3.10 required)
PYTHON_BIN="${PYTHON:-}"
if [ -z "$PYTHON_BIN" ]; then
  if command -v uv >/dev/null 2>&1; then
    if uv python find ">=3.10,<3.13" >/dev/null 2>&1; then
      PYTHON_BIN="$(uv python find '>=3.10,<3.13')"
    elif uv python find ">=3.10" >/dev/null 2>&1; then
      PYTHON_BIN="$(uv python find '>=3.10')"
    fi
  fi
  if [ -z "$PYTHON_BIN" ]; then
    if command -v python3.12 >/dev/null 2>&1; then
      PYTHON_BIN="$(command -v python3.12)"
    elif command -v python3.11 >/dev/null 2>&1; then
      PYTHON_BIN="$(command -v python3.11)"
    elif command -v python3.10 >/dev/null 2>&1; then
      PYTHON_BIN="$(command -v python3.10)"
    elif command -v python3 >/dev/null 2>&1; then
      PYTHON_BIN="$(command -v python3)"
    else
      echo "ERROR: python3 not found." >&2
      exit 1
    fi
  fi
fi

echo "Checking Python version with $PYTHON_BIN..."
"$PYTHON_BIN" -c 'import sys; assert sys.version_info >= (3, 10), f"Python 3.10+ required, got {sys.version}"' || {
  echo "ERROR: Python 3.10 or newer is required." >&2
  exit 1
}
echo "Python version check OK ($("$PYTHON_BIN" --version))."

# 2. Create virtual environment if absent
if [ ! -d "$VENV_DIR" ]; then
  echo "Creating virtual environment at $VENV_DIR..."
  if command -v uv >/dev/null 2>&1; then
    uv venv -q --python "$PYTHON_BIN" "$VENV_DIR"
  else
    "$PYTHON_BIN" -m venv "$VENV_DIR"
  fi
else
  echo "Virtual environment already exists at $VENV_DIR."
fi

# 3. Determine pip installer
if command -v uv >/dev/null 2>&1; then
  PIP_CMD=("uv" "pip" "install" "--python" "$VENV_DIR/bin/python")
else
  "$VENV_DIR/bin/python" -m pip install --upgrade pip
  PIP_CMD=("$VENV_DIR/bin/pip" "install")
fi

# 4. Install all requirements*.txt across the repository
echo "Installing Python requirements across all components..."
while IFS= read -r req_file; do
  echo "  -> Installing $(realpath --relative-to="$ROOT_DIR" "$req_file")..."
  "${PIP_CMD[@]}" -r "$req_file"
done < <(find "$ROOT_DIR" -type f -name "requirements*.txt" ! -path "*/node_modules/*" ! -path "*/.venv/*" | sort)

# 5. Install Node.js frontend dependencies
echo "Installing web frontend dependencies with npm ci..."
if [ -d "$ROOT_DIR/marketplace/web" ]; then
  if command -v npm >/dev/null 2>&1; then
    (cd "$ROOT_DIR/marketplace/web" && npm ci)
  else
    echo "WARNING: npm not found. Please install Node.js 22+ and npm to run the web frontend." >&2
  fi
fi

echo ""
echo "======================================================================"
echo " Setup completed successfully!"
echo "======================================================================"
echo "Next steps:"
echo "  1. Ensure Algorand LocalNet is running:"
echo "       algokit localnet start"
echo "  2. Start the marketplace (gateway, 16 MCP servers, and Web UI):"
echo "       ./start.sh"
echo "  3. Check service health and port bindings:"
echo "       ./status.sh"
echo "  4. Open the Web UI in your browser:"
echo "       http://localhost:5173"
echo "  5. Stop services when finished:"
echo "       ./stop.sh"
echo "======================================================================"
