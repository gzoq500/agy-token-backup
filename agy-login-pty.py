#!/usr/bin/python3
"""
PTY-based login flow for Antigravity CLI.
Menampilkan link OAuth2, menyimpan ke /tmp/agy-auth-url.txt,
menunggu authorization code di /tmp/agy-code.txt, lalu menyuntikkannya ke agy.
"""
import pty, os, sys, fcntl, termios, struct, select, time, subprocess, re, json

LOG = "/tmp/agy-login.log"
open(LOG, "w").close()
for f_ in ("/tmp/agy-code.txt", "/tmp/agy-auth-url.txt"):
    if os.path.exists(f_):
        try: os.remove(f_)
        except: pass

def clean(t):
    return re.sub(r'\x1b\[[0-9;?]*[a-zA-Z]', '', t)

def extract_url(text):
    m = re.search(r'https://accounts\.google\.com/o/oauth2/auth\?\S+', text.replace("\n", ""))
    if m:
        return m.group(0).rstrip("→ ").split("\x07")[0]
    return None

master, slave = pty.openpty()
fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 50, 140, 0, 0))

env_vars = {
    **os.environ,
    "PATH": "/root/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin",
    "TERM": "xterm-256color",
    "AGY_CLI_DISABLE_AUTO_UPDATE": "1",
    "ALL_PROXY": "socks5://127.0.0.1:1080",
    "HTTPS_PROXY": "socks5://127.0.0.1:1080",
    "HTTP_PROXY": "socks5://127.0.0.1:1080",
    "no_proxy": "localhost,127.0.0.1,::1",
    "NO_PROXY": "localhost,127.0.0.1,::1",
    "DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/0/bus"
}

proc = subprocess.Popen(
    ["/root/.local/bin/agy"],
    stdin=slave, stdout=slave, stderr=slave,
    env=env_vars
)
os.close(slave)

with open("/tmp/agy-proc-pid", "w") as f:
    f.write(str(proc.pid))

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

print("=== AGY LOGIN STARTED ===")
sys.stdout.flush()

# Step 1: Initial screen
read_all(6)
os.write(master, b"\r")
time.sleep(2)

# Step 2: Handle menu
out1 = read_all(10)
text1 = clean(out1.decode(errors="replace"))
with open(LOG, "ab") as f:
    f.write(out1)

if "not signed in" in text1.lower() or "select login method" in text1.lower() or "oauth" in text1.lower():
    print("Memilih: 1. Google OAuth")
    sys.stdout.flush()
    os.write(master, b"\r")
    time.sleep(3)
    out1b = read_all(12)
    with open(LOG, "ab") as f:
        f.write(out1b)
    text1 += clean(out1b.decode(errors="replace"))

# Step 3: Extract auth URL
auth_url = extract_url(text1)
if auth_url:
    with open("/tmp/agy-auth-url.txt", "w") as f:
        f.write(auth_url)
    print("\n=== AUTHORIZATION URL DITEMUKAN ===")
    print(auth_url)
    print("\nURL tersimpan di /tmp/agy-auth-url.txt")
    print("Menunggu authorization code di /tmp/agy-code.txt (timeout 30 menit)...")
    sys.stdout.flush()
else:
    print("\n=== URL belum terbaca dari output TUI ===")
    print(text1[-500:])
    sys.stdout.flush()

# Step 4: Verification URL check
if "signin/continue" in text1:
    verify_url = re.search(r'https://accounts\.google\.com/signin/continue\?\S+', text1.replace("\n",""))
    if verify_url:
        v_url = verify_url.group(0).rstrip("→ ").split("\x07")[0]
        with open("/tmp/agy-verify-url.txt", "w") as f:
            f.write(v_url)
        print("\n=== BROWSER VERIFICATION NEEDED ===")
        print(v_url)
        sys.stdout.flush()

# Step 5: Polling code
deadline = time.time() + 1800
code_sent = False

while time.time() < deadline and proc.poll() is None:
    if os.path.exists("/tmp/agy-code.txt"):
        code = open("/tmp/agy-code.txt").read().strip()
        if code:
            print(f"\n=== MENGIRIM AUTHORIZATION CODE ({len(code)} chars) ===")
            sys.stdout.flush()
            for ch in code:
                os.write(master, ch.encode())
                time.sleep(0.005)
            os.write(master, b"\r")
            code_sent = True
            try: os.remove("/tmp/agy-code.txt")
            except: pass
            time.sleep(8)
            out2 = read_all(30)
            with open(LOG, "ab") as f:
                f.write(out2)
            text2 = clean(out2.decode(errors="replace"))
            print("=== HASIL LOGIN ===")
            print(text2[-1500:])
            sys.stdout.flush()
            break
    out = read_all(1)
    if out:
        with open(LOG, "ab") as f:
            f.write(out)

if not code_sent:
    print("\nTIMEOUT: Code tidak diterima.")
    try: proc.kill()
    except: pass
sys.exit(0)
