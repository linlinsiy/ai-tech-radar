#!/bin/bash
set -e

APP_DIR="/app/001804/internal"

echo "Creating application directories..."
mkdir -p "$APP_DIR/logs"
mkdir -p "$APP_DIR/logs/xxl-job"
mkdir -p "$APP_DIR/secrets"

echo "Setting permissions..."
chmod 755 "$APP_DIR"
chmod 700 "$APP_DIR/secrets"
chmod +x "$APP_DIR/deploy/start.sh"
chmod +x "$APP_DIR/deploy/install.sh"

echo "Installation completed. Please configure secrets/.env and start the service with:"
echo "  cd $APP_DIR && ./deploy/start.sh"
echo ""
echo "For systemd service (requires root):"
echo "  sudo cp deploy/ai-radar-internal.service /etc/systemd/system/"
echo "  sudo systemctl daemon-reload"
echo "  sudo systemctl enable ai-radar-internal"
echo "  sudo systemctl start ai-radar-internal"