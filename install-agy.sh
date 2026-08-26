#!/bin/bash
# Download dan install Antigravity CLI
set -e

echo "=== Downloading Antigravity CLI ==="
# Dapatkan binary terbaru
curl -sSL https://github.com/google-golang/antigravity/releases/latest/download/agy-linux-amd64 -o /tmp/agy
chmod +x /tmp/agy
mkdir -p /root/.local/bin
mv /tmp/agy /root/.local/bin/agy
echo "agy installed di: $(which agy)"
agy --version 2>&1 || true
