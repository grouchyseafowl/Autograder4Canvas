#!/bin/bash
# Canvas Autograder Launcher (macOS / Linux)
cd "$(dirname "$0")"

PYTHON_CMD=""
if command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
elif command -v python &>/dev/null && python --version 2>&1 | grep -q "Python 3"; then
    PYTHON_CMD="python"
fi

if [ -z "$PYTHON_CMD" ]; then
    echo "Python 3 not found. Install from https://www.python.org/downloads/"
    exit 1
fi

exec "$PYTHON_CMD" src/bootstrap.py "$@"
