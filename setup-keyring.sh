#!/bin/bash
# Setup GNOME Keyring untuk headless Ubuntu/Debian VPS
# Run sekali di VPS baru
set -e

echo "=== Installing gnome-keyring & libsecret-tools ==="
apt-get update -qq 2>/dev/null || true
apt-get install -y -qq gnome-keyring libsecret-tools python3-secretstorage python3-dbus 2>&1 | tail -2

echo "=== Starting gnome-keyring-daemon (unlocked with empty password) ==="
export DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/0/bus"
mkdir -p /run/user/0

# Start daemon dan unlock collection login
echo -n "" | gnome-keyring-daemon --unlock --components=secrets 2>&1 || true
sleep 2
echo -n "" | gnome-keyring-daemon --start --components=secrets 2>&1 || true
sleep 2

echo "=== Verifikasi Secret Service ==="
/usr/bin/python3 <<'PYEOF'
import dbus
bus = dbus.SessionBus()
svc = bus.get_object("org.freedesktop.secrets", "/org/freedesktop/secrets")
iface = dbus.Interface(svc, "org.freedesktop.DBus.Properties")
print("Secret Service status:", iface.Get("org.freedesktop.Secret.Service", "Open"))
collections = iface.Get("org.freedesktop.Secret.Service", "Collections")
print("Collections:", [str(c) for c in collections])
PYEOF

echo "=== GNOME Keyring siap! ==="
