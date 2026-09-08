#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ $EUID -ne 0 ]]; then
  echo "Run this script with sudo/root because it installs systemd units."
  exit 1
fi

if [[ ! -f "$PROJECT_DIR/.env" ]]; then
  echo "Missing $PROJECT_DIR/.env. Copy .env.example to .env and configure it first."
  exit 1
fi

if [[ ! -x "$PROJECT_DIR/.venv/bin/streamlit" ]]; then
  echo "Missing virtual environment. Create .venv and install requirements first."
  exit 1
fi

sed "s|__PROJECT_DIR__|$PROJECT_DIR|g" "$PROJECT_DIR/deploy/cloudpay-streamlit.service" > /etc/systemd/system/cloudpay-streamlit.service
sed "s|__PROJECT_DIR__|$PROJECT_DIR|g" "$PROJECT_DIR/deploy/cloudpay-ipn.service" > /etc/systemd/system/cloudpay-ipn.service

systemctl daemon-reload
systemctl enable --now cloudpay-streamlit cloudpay-ipn
systemctl --no-pager --full status cloudpay-streamlit cloudpay-ipn || true

echo
echo "Services installed. Next add deploy/nginx-pesapal-demo.conf to the existing api.xerinmarketplace.com server block and reload Nginx."
