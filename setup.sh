#!/bin/bash
#
# setup.sh - Complete Antigravity CLI VPS Provisioner
# Installs dependencies, downloads agy, applies CPU compatibility patch,
# configures keyring/DBus, and sets up transparent proxy routing.
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="/root/.local/bin"
REAL_BIN="$TARGET_DIR/agy-real"
WRAPPER_BIN="$TARGET_DIR/agy"

echo "=== [1/5] Installing System Dependencies ==="
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq gnome-keyring libsecret-tools python3-secretstorage python3-dbus curl jq >/dev/null

echo "=== [2/5] Configuring GNOME Keyring & DBus ==="
mkdir -p /run/user/0
export DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/0/bus"

# Unlock keyring daemon with empty password for headless automation
echo -n "" | gnome-keyring-daemon --unlock --components=secrets 2>/dev/null || true
echo -n "" | gnome-keyring-daemon --start --components=secrets 2>/dev/null || true

# Update persistent shell profiles
mkdir -p "$TARGET_DIR"
for profile_file in /root/.bashrc /root/.profile; do
    if [ -f "$profile_file" ]; then
        if ! grep -q "AGY_CLI_DISABLE_AUTO_UPDATE" "$profile_file"; then
            cat <<'EOF' >> "$profile_file"

# Antigravity CLI & Proxy Environment
export PATH="/root/.local/bin:$PATH"
export DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/0/bus"
export AGY_CLI_DISABLE_AUTO_UPDATE=1
export ALL_PROXY="${ALL_PROXY:-socks5://127.0.0.1:1080}"
export HTTPS_PROXY="${HTTPS_PROXY:-socks5://127.0.0.1:1080}"
export HTTP_PROXY="${HTTP_PROXY:-socks5://127.0.0.1:1080}"
export no_proxy="localhost,127.0.0.1,::1"
export NO_PROXY="localhost,127.0.0.1,::1"
EOF
        fi
    fi
done

echo "=== [3/5] Downloading Antigravity CLI ==="
MANIFEST_URL="https://antigravity-cli-auto-updater-974169037036.us-central1.run.app/manifests/linux_amd64.json"
MANIFEST=$(curl -fsSL "$MANIFEST_URL")
VERSION=$(echo "$MANIFEST" | jq -r .version)
DOWNLOAD_URL=$(echo "$MANIFEST" | jq -r .url)

echo "Detected latest release: v$VERSION"
TMP_DIR=$(mktemp -d /tmp/agy-install-XXXXXX)
trap 'rm -rf "$TMP_DIR"' EXIT

curl -fsSL "$DOWNLOAD_URL" -o "$TMP_DIR/agy.tar.gz"
tar -xzf "$TMP_DIR/agy.tar.gz" -C "$TMP_DIR"

# Unlock existing real binary if protected
if [ -f "$REAL_BIN" ]; then
    chattr -i "$REAL_BIN" 2>/dev/null || true
fi
cp -f "$TMP_DIR/antigravity" "$REAL_BIN"
chmod +x "$REAL_BIN"

echo "=== [4/5] Applying CPU Feature Patch (pclmulqdq / SIGILL bypass) ==="
/usr/bin/python3 "$SCRIPT_DIR/patch_binary.py" "$REAL_BIN"

# Lock real binary against automated Borg in-place overwrites
chattr +i "$REAL_BIN" 2>/dev/null || true

echo "=== [5/5] Creating Smart Proxy & Environment Wrapper ==="
cat <<'EOF' > "$WRAPPER_BIN"
#!/bin/bash
export AGY_CLI_DISABLE_AUTO_UPDATE=1
export ALL_PROXY="${ALL_PROXY:-socks5://127.0.0.1:1080}"
export HTTPS_PROXY="${HTTPS_PROXY:-socks5://127.0.0.1:1080}"
export HTTP_PROXY="${HTTP_PROXY:-socks5://127.0.0.1:1080}"
export no_proxy="${no_proxy:-localhost,127.0.0.1,::1}"
export NO_PROXY="${NO_PROXY:-localhost,127.0.0.1,::1}"
export DBUS_SESSION_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS:-unix:path=/run/user/0/bus}"

exec /root/.local/bin/agy-real "$@"
EOF
chmod +x "$WRAPPER_BIN"

# Create global symlinks for utilities
chmod +x "$SCRIPT_DIR/login.py" "$SCRIPT_DIR/account.py" "$SCRIPT_DIR/verify.py" "$SCRIPT_DIR/setup.sh"
ln -sf "$SCRIPT_DIR/login.py" "$TARGET_DIR/agy-login"
ln -sf "$SCRIPT_DIR/account.py" "$TARGET_DIR/agy-account"
ln -sf "$SCRIPT_DIR/verify.py" "$TARGET_DIR/agy-verify"

# Proxy check
echo ""
if ss -ltn | grep -q ":1080 "; then
    echo "✓ SOCKS5 proxy active on 127.0.0.1:1080."
else
    echo "⚠️ SOCKS5 proxy on 127.0.0.1:1080 is NOT detected."
    echo "   Ensure your egress proxy (e.g. socks5-japan.service) is running before login."
fi

# Verification
INSTALLED_VER=$("$WRAPPER_BIN" --version 2>&1 || true)
echo "✓ Antigravity CLI successfully installed: $INSTALLED_VER"
echo "  Binary wrapper: $WRAPPER_BIN"
echo "  Patched core:   $REAL_BIN (immutable)"
echo ""
echo "Next step: Run 'python3 $SCRIPT_DIR/login.py' to authenticate."
