#!/bin/bash
# RESTORE script — jalankan di VPS baru untuk langsung bisa pakai agy tanpa login ulang
# Repo: gzoq500/agy-token-backup
set -e

REPO="https://github.com/gzoq500/agy-token-backup.git"
GITHUB_USER="gzoq500"

echo "=== Step 1: Install GNOME Keyring ==="
apt-get update -qq
apt-get install -y -qq gnome-keyring libsecret-tools python3-secretstorage python3-dbus curl git

echo "=== Step 2: Start Keyring Daemon ==="
export DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/0/bus"
mkdir -p /run/user/0
echo -n "" | gnome-keyring-daemon --unlock --components=secrets 2>&1 || true
sleep 2
echo -n "" | gnome-keyring-daemon --start --components=secrets 2>&1 || true
sleep 2

echo "=== Step 3: Install Antigravity CLI ==="
curl -sSL https://github.com/google-golang/antigravity/releases/latest/download/agy-linux-amd64 -o /root/.local/bin/agy
chmod +x /root/.local/bin/agy

echo "=== Step 4: Restore token from keyring backup ==="
cd /tmp
git clone --depth=1 $REPO agy-backup 2>&1 | tail -2
cd agy-backup

# Restore token ke keyring (jika file restore-token.json ada di repo)
# NOTE: Token asli TIDAK disimpan di GitHub (security). 
# Ini hanya metadata. Untuk restore penuh, login manual sekali lewat PTY.
echo ""
echo "============================================"
echo "RESTORE SELESAI — agy terpasang."
echo "Untuk login otomatis, jalankan:"
echo "  python3 /tmp/agy-backup/restore-login.py"
echo ""
echo "Atau login manual jika token tidak tersedia."
echo "============================================"
echo "PATH export untuk shell ini:"
export PATH="/root/.local/bin:$PATH"
export DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/0/bus"
echo 'export PATH="/root/.local/bin:$PATH"' >> /root/.bashrc
echo 'export DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/0/bus"' >> /root/.bashrc
echo "============================================"
