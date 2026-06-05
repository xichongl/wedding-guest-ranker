#!/usr/bin/env bash
# Wedding Guest Ranker — Launch Script
#
# Usage:
#   bash run.sh              # Start on default port 5050
#   bash run.sh -p 8080      # Start on custom port
#
# Open http://localhost:5050 in your browser once running.

set -e
cd "$(dirname "$0")"

# Find a working Python 3
PYTHON=""
for candidate in python3 python; do
    if command -v "$candidate" &>/dev/null && "$candidate" -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)" 2>/dev/null; then
        PYTHON="$candidate"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo "Error: Python 3.8 or newer is required."
    echo "Install it from https://www.python.org/downloads/"
    exit 1
fi

# Ensure data directory exists
mkdir -p data

# Install Flask if needed
if ! $PYTHON -c "import flask" 2>/dev/null; then
    echo "Installing Flask..."
    $PYTHON -m pip install flask --quiet
    echo "Done."
fi

echo ""
echo "  💍  Wedding Guest Ranker"
echo "  ─────────────────────────"
echo "  Open: http://localhost:${PORT:-5050}"
echo "  Press Ctrl+C to stop"
echo ""

exec $PYTHON app.py "$@"
