#!/bin/bash
set -e

APP_DIR="/app/001804/internal"
VENV_DIR="$APP_DIR/venv"
APP_PORT=${SERVER_PORT:-9001}

cd "$APP_DIR"

if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    python3.11 -m venv "$VENV_DIR"
fi

echo "Activating virtual environment..."
source "$VENV_DIR/bin/activate"

echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "Starting AI Radar Internal Service on port $APP_PORT..."
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "$APP_PORT" --log-level info