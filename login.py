#!/usr/bin/env python3
"""
login.py - Unified Antigravity CLI Login & 2-Step Verification Helper.

Handles:
1. PTY-based OAuth flow to extract Step 1 Authorization Link.
2. Injects authorization code from interactive prompt, CLI argument, or /tmp/agy-code.txt.
3. Automatically executes API eligibility probe.
4. If Google triggers Step 2 verification (VALIDATION_REQUIRED / signin/continue),
   extracts and displays Step 2 Verification Link, then waits and verifies.
5. Backs up the token labeled by email address.
"""

import os
import sys
import pty
import time
import select
import fcntl
import termios
import struct
import subprocess
import re
import json
import base64
import argparse

AUTH_URL_FILE = "/tmp/agy-auth-url.txt"
VERIFY_URL_FILE = "/tmp/agy-verify-url.txt"
CODE_FILE = "/tmp/agy-code.txt"
VERIFY_DONE_FILE = "/tmp/agy-verify-done"
LOG_FILE = "/tmp/agy-login.log"
TOKEN_PATH = "/root/.gemini/antigravity-cli/antigravity-oauth-token"
BACKUP_DIR = "/root/.gemini/antigravity-cli/token-backups"
WRAPPER_BIN = "/root/.local/bin/agy"
REAL_BIN = "/root/.local/bin/agy-real"

def clean_ansi(text):
    return re.sub(r'\x1b\[[0-9;?]*[a-zA-Z]', '', text)

def extract_url(pattern, text):
    m = re.search(pattern, text.replace("\n", ""))
    if m:
        return m.group(0).rstrip("→ ").split("\x07")[0].split(" ")[0].strip()
    return None

def extract_email_from_token(token_file):
    if not os.path.exists(token_file):
        return None
    try:
        with open(token_file, "r") as f:
            data = json.load(f)
        id_token = data.get("id_token", "")
        if id_token and "." in id_token:
            payload_b64 = id_token.split(".")[1]
            payload_b64 += "=" * (-len(payload_b64) % 4)
            claims = json.loads(base64.urlsafe_b64decode(payload_b64))
            return claims.get("email")
    except Exception:
        pass
    return None

def run_probe():
    """Runs a test query via wrapper to verify API eligibility."""
    try:
        proc = subprocess.run(
            [WRAPPER_BIN, "--dangerously-skip-permissions", "-p", "Reply with: AGY_AUTH_VERIFIED"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=45
        )
        return proc.stdout
    except Exception as e:
        return f"Probe error: {e}"

def main():
    parser = argparse.ArgumentParser(description="Antigravity CLI Login & Verification Flow")
    parser.add_argument("--code", help="Direct authorization code from Step 1")
    parser.add_argument("--timeout", type=int, default=1800, help="Code wait timeout in seconds (default 1800)")
    parser.add_argument("--no-probe", action="store_true", help="Skip Step 2 eligibility check")
    args = parser.parse_args()

    # Pre-clean temporary coordination files
    for p in (AUTH_URL_FILE, VERIFY_URL_FILE, CODE_FILE, VERIFY_DONE_FILE):
        if os.path.exists(p):
            try: os.remove(p)
            except: pass

    # Prepare PTY
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 50, 140, 0, 0))

    env = {
        **os.environ,
        "PATH": "/root/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin",
        "TERM": "xterm-256color",
        "AGY_CLI_DISABLE_AUTO_UPDATE": "1",
        "ALL_PROXY": os.environ.get("ALL_PROXY", "socks5://127.0.0.1:1080"),
        "HTTPS_PROXY": os.environ.get("HTTPS_PROXY", "socks5://127.0.0.1:1080"),
        "HTTP_PROXY": os.environ.get("HTTP_PROXY", "socks5://127.0.0.1:1080"),
        "no_proxy": "localhost,127.0.0.1,::1",
        "DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/0/bus"
    }

    bin_to_run = REAL_BIN if os.path.exists(REAL_BIN) else WRAPPER_BIN
    proc = subprocess.Popen(
        [bin_to_run],
        stdin=slave, stdout=slave, stderr=slave,
        env=env
    )
    os.close(slave)

    with open("/tmp/agy-proc-pid", "w") as f:
        f.write(str(proc.pid))

    def read_output(duration):
        accumulated = b""
        end_time = time.time() + duration
        while time.time() < end_time:
            r, _, _ = select.select([master], [], [], 0.5)
            if r:
                try:
                    chunk = os.read(master, 8192)
                    if not chunk: break
                    accumulated += chunk
                except OSError:
                    break
            if proc.poll() is not None:
                break
        with open(LOG_FILE, "ab") as f:
            f.write(accumulated)
        return accumulated

    print("========================================================================")
    print("           ANTIGRAVITY CLI LOGIN & VERIFIKASI DUA LANGKAH               ")
    print("========================================================================")
    sys.stdout.flush()

    # Initial wait & bypass first screen
    read_output(6)
    os.write(master, b"\r")
    time.sleep(2)

    # Menu detection
    out_menu = clean_ansi(read_output(10).decode("utf-8", "replace"))
    if "oauth" in out_menu.lower() or "select login method" in out_menu.lower() or "not signed in" in out_menu.lower():
        os.write(master, b"\r")
        time.sleep(3)
        read_output(10)

    # Extract OAuth URL
    with open(LOG_FILE, "rb") as f:
        full_log = clean_ansi(f.read().decode("utf-8", "replace"))

    auth_url = extract_url(r'https://accounts\.google\.com/o/oauth2/auth\?\S+', full_log)
    if not auth_url:
        print("[ERROR] Authorization URL tidak ditemukan di antarmuka TUI.", file=sys.stderr)
        proc.kill()
        sys.exit(1)

    with open(AUTH_URL_FILE, "w") as f:
        f.write(auth_url)

    print("\n[LANGKAH 1] GOOGLE OAUTH AUTHORIZATION LINK")
    print("Buka tautan ini di browser Anda dan login dengan akun target:")
    print("------------------------------------------------------------------------")
    print(auth_url)
    print("------------------------------------------------------------------------")
    print(f"(Tautan juga tersimpan di {AUTH_URL_FILE})")
    print("Menunggu authorization code...")
    sys.stdout.flush()

    # Receive code
    auth_code = args.code
    deadline = time.time() + args.timeout

    if not auth_code:
        # Check if stdin is a tty for interactive prompt
        if sys.stdin.isatty():
            try:
                auth_code = input("\nMasukkan Authorization Code: ").strip()
            except (KeyboardInterrupt, EOFError):
                pass

    if not auth_code:
        while time.time() < deadline and proc.poll() is None:
            if os.path.exists(CODE_FILE):
                try:
                    c = open(CODE_FILE).read().strip()
                    if c:
                        auth_code = c
                        os.remove(CODE_FILE)
                        break
                except:
                    pass
            read_output(1)

    if not auth_code:
        print("[TIMEOUT] Authorization code tidak diterima dalam batas waktu.", file=sys.stderr)
        proc.kill()
        sys.exit(1)

    print(f"\n[+] Mengirimkan authorization code ({len(auth_code)} karakter)...")
    for char in auth_code:
        os.write(master, char.encode())
        time.sleep(0.005)
    os.write(master, b"\r")

    # Wait for token generation
    token_saved = False
    for _ in range(30):
        time.sleep(1)
        if os.path.exists(TOKEN_PATH) and os.path.getsize(TOKEN_PATH) > 100:
            token_saved = True
            break
        read_output(1)

    try: proc.kill()
    except: pass

    if not token_saved:
        print("[ERROR] Token gagal dibuat oleh Antigravity CLI. Cek /tmp/agy-login.log.", file=sys.stderr)
        sys.exit(1)

    email = extract_email_from_token(TOKEN_PATH) or "unknown_account"
    print(f"[✓] Autentikasi OAuth berhasil! Akun: {email}")

    # Step 2: Account Eligibility Check & Verification Link
    if not args.no_probe:
        print("\n[Memeriksa Kelayakan Akun via API Probe...]")
        probe_res = run_probe()

        if "AGY_AUTH_VERIFIED" in probe_res:
            print("[✓] Akun langsung aktif! Tidak memerlukan verifikasi browser tambahan.")
        elif "signin/continue" in probe_res or "Eligibility check failed" in probe_res:
            verify_url = extract_url(r'https://accounts\.google\.com/signin/continue\?\S+', probe_res)
            if verify_url:
                with open(VERIFY_URL_FILE, "w") as f:
                    f.write(verify_url)

                print("\n========================================================================")
                print("[LANGKAH 2] VERIFIKASI AKUN DIBUTUHKAN (2x Verifikasi)")
                print("Akun Google ini memerlukan konfirmasi satu kali di browser.")
                print("Buka tautan ini di browser dengan akun yang sama:")
                print("------------------------------------------------------------------------")
                print(verify_url)
                print("------------------------------------------------------------------------")
                print(f"(Tautan tersimpan di {VERIFY_URL_FILE})")
                print("========================================================================")
                sys.stdout.flush()

                # Wait for user confirmation or verification completion
                if sys.stdin.isatty():
                    input("\nTekan [ENTER] setelah menyelesaikan verifikasi di browser...")
                else:
                    print("Menunggu konfirmasi verifikasi (/tmp/agy-verify-done atau polling probe)...")
                    v_deadline = time.time() + 600
                    verified = False
                    while time.time() < v_deadline:
                        if os.path.exists(VERIFY_DONE_FILE):
                            break
                        time.sleep(6)
                        p_check = run_probe()
                        if "AGY_AUTH_VERIFIED" in p_check:
                            verified = True
                            break
                    if not verified and not os.path.exists(VERIFY_DONE_FILE):
                        print("Timeout menunggu verifikasi browser. Silakan jalankan test manual.")

                # Re-verify probe
                final_check = run_probe()
                if "AGY_AUTH_VERIFIED" in final_check:
                    print("\n[✓] Verifikasi browser berhasil! Akun telah sepenuhnya di-unblock.")
                else:
                    print(f"\n[!] Status probe setelah verifikasi:\n{final_check}")
        else:
            print(f"Hasil probe: {probe_res}")

    # Backup token
    os.makedirs(BACKUP_DIR, exist_ok=True)
    clean_email = email.replace("@", "_at_")
    backup_file = os.path.join(BACKUP_DIR, f"{clean_email}.oauth-token")
    try:
        subprocess.run(["cp", "-f", TOKEN_PATH, backup_file], check=True)
        print(f"[✓] Token berhasil dicadangkan ke: {backup_file}")
    except Exception as e:
        print(f"[!] Gagal mencadangkan token: {e}")

    print("\n========================================================================")
    print("PROSES SELESAI — Antigravity CLI siap digunakan:")
    print("  agy --dangerously-skip-permissions -p 'Halo'")
    print("========================================================================")

if __name__ == "__main__":
    main()
