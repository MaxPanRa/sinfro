#!/bin/bash

set -u

cd "$(dirname "$0")"

PYTHON_EXE="$PWD/.venv/bin/python"

if [ ! -x "$PYTHON_EXE" ]; then
    echo "Creating virtual environment..."
    if command -v python3 >/dev/null 2>&1; then
        python3 -m venv .venv
    elif command -v python >/dev/null 2>&1; then
        python -m venv .venv
    else
        echo "Could not find Python. Please install Python 3.11 or newer."
        read -r -p "Press Enter to close..."
        exit 1
    fi
fi

if [ ! -x "$PYTHON_EXE" ]; then
    echo "Could not create .venv. Please install Python 3.11 or newer."
    read -r -p "Press Enter to close..."
    exit 1
fi

if ! "$PYTHON_EXE" -c "import PySide6" >/dev/null 2>&1; then
    echo "Installing dependencies..."
    "$PYTHON_EXE" -m pip install --upgrade pip || {
        read -r -p "Press Enter to close..."
        exit 1
    }
    "$PYTHON_EXE" -m pip install -r requirements.txt || {
        read -r -p "Press Enter to close..."
        exit 1
    }
fi

echo "Starting Job Radar..."
"$PYTHON_EXE" run_job_radar.py
STATUS=$?

if [ "$STATUS" -ne 0 ]; then
    echo
    echo "Job Radar could not start. Review the message above."
    read -r -p "Press Enter to close..."
fi

exit "$STATUS"
