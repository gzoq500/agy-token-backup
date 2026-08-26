#!/usr/bin/env python3
"""
PTY-based login flow for Antigravity CLI.
Menampilkan link OAuth2, menunggu authorization code, lalu menyuntikkannya ke agy.
Setelah login, token tersimpan otomatis di GNOME Keyring (service: gemini, username: antigravity).

Usage:
  python3 agy-login-pty.py            # Interactive mode - prints URL, waits for /tmp/agy-code.txt
  python3 agy-login-pty.py --code "4/0..."  # Provide code directly

Requirements:
  - agy di $PATH
  - DBUS_SESSION_BUS_ADDRESS ter-set
  - /tmp/agy-code.txt berisi authorization code
"""
import pty, os, sys, fcntl, termios, struct, select, time, subprocess, re, json

LOG = "/tmp/agy-login-interactive.log"
open(LOG, "w").close()
for f_ in ("/tmp/agy-code.txt",):
    if os.path.exists(f_): os.remove(f_)

def clean(t):
    """Strip ANSI escape codes."""
    return re.sub(r'\x1b\[[0-9;?]*[a-zA-Z]', '', t)

def extract_url(text):
    """Extract Google OAuth URL from agy output."""
    m = re.search(r'https://accounts\.google\.com/o/oauth2/auth\?\S+', text.replace("\n", ""))
    if m:
        url = m.group(0).rstrip("→ ").split("\x07")[0]
        return url
    return None

master, slave = pty.openpty()
fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 50, 140, 0, 0))
proc = subprocess.Popen(
    ["/root/.local/bin/agy"],
    stdin=slave, stdout=slave, stderr=slave,
    env={**os.environ, "PATH": "/root/.local/bin:/usr/bin:/bin", "TERM": "xterm-256color"}
)
os.close(slave)
time.sleep(1)

def read_all(sec):
    out = b""
    end = time.time() + sec
    while time.time() < end:
        r, _, _ = select.select([master], [], [], 0.5)
        if r:
            try:
                d = os.read(master, 8192)
                if not d: break
                out += d
            except OSError:
                break
        if proc.poll() is not None:
            break
    return out

# Step 1: Accept any initial prompts (e.g., color scheme selection)
read_all(8)
os.write(master, b"\r")
time.sleep(2)

# Step 2: Handle "Welcome" screen
out1 = read_all(10)
text1 = clean(out1.decode(errors="replace"))

with open(LOG, "ab") as f:
    f.write(out1)

# Check if we're at login menu
if "not signed in" in text1.lower() or "Select login method" in text1:
    os.write(master, b"\r")  # Select "1. Google OAuth"
    print("=== Pilih Google OAuth ===")
    time.sleep(3)
    out1b = read_all(12)
    with open(LOG, "ab") as f:
        f.write(out1b)
    text1 += clean(out1b.decode(errors="replace"))

# Step 3: Extract auth URL
auth_url = extract_url(text1)
if auth_url:
    print("=== AUTHORIZATION URL ===")
    print(auth_url)
    print("\nBuka link di atas di browser, login goxgavavo@gmail.com,")
    print("salin authorization code, simpan ke /tmp/agy-code.txt")
else:
    print("=== WARNING: URL tidak ditemukan ===")
    print(text1[-500:])

# Step 4: Handle verification challenge (jika ada browser verification link)
if "signin/continue" in text1:
    verify_url = re.search(r'https://accounts\.google\.com/signin/continue\?\S+', text1.replace("\n",""))
    if verify_url:
        print("\n=== BROWSER VERIFICATION NEEDED ===")
        print(verify_url.group(0).rstrip("→ ").split("\x07")[0])

# Step 5: Polling for authorization code
print("\nMenunggu authorization code di /tmp/agy-code.txt ... (maksimal 15 menit)")
deadline = time.time() + 900
code_sent = False

while time.time() < deadline and proc.poll() is None:
    if os.path.exists("/tmp/agy-code.txt"):
        code = open("/tmp/agy-code.txt").read().strip()
        if code:
            print(f"\n=== MENGIRIM KODE ({len(code)} chars) ===")
            for ch in code:
                os.write(master, ch.encode())
                time.sleep(0.005)
            os.write(master, b"\r")
            code_sent = True
            try:
                os.remove("/tmp/agy-code.txt")
            except:
                pass
            time.sleep(8)
            out2 = read_all(30)
            with open(LOG, "ab") as f:
                f.write(out2)
            print("=== LOGIN RESULT ===")
            text2 = clean(out2.decode(errors="replace"))
            print(text2[-1500:])
            break
    out = read_all(1)
    if out:
        with open(LOG, "ab") as f:
            f.write(out)

# Save PID
with open("/tmp/agy-proc-pid", "w") as f:
    f.write(str(proc.pid))

if not code_sent:
    print("\nTIMEOUT: authorization code tidak diterima dalam 15 menit.")
    proc.kill()
sys.exit(0)
