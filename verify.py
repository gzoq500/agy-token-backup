#!/usr/bin/env python3
"""
verify.py - Quick Health Check for Antigravity CLI Setup
Verifies binary, proxy egress location, active account token, and runs a test turn.
"""

import os
import sys
import subprocess
import json
import base64
import urllib.request

TOKEN_PATH = "/root/.gemini/antigravity-cli/antigravity-oauth-token"
WRAPPER_BIN = "/root/.local/bin/agy"

def get_proxy_egress():
    try:
        # Check via curl with socks5 proxy
        out = subprocess.check_output(
            ["curl", "-sS", "--proxy", "socks5h://127.0.0.1:1080", "-m", "6", "http://ip-api.com/json/"],
            text=True
        )
        data = json.loads(out)
        return f"{data.get('country')} ({data.get('query')})"
    except Exception:
        return "Failed / Inactive"

def get_current_email():
    if not os.path.exists(TOKEN_PATH):
        return None
    try:
        with open(TOKEN_PATH) as f:
            d = json.load(f)
        id_token = d.get("id_token", "")
        if id_token and "." in id_token:
            p = id_token.split(".")[1]
            p += "=" * (-len(p) % 4)
            return json.loads(base64.urlsafe_b64decode(p)).get("email")
    except Exception:
        pass
    return "Unknown"

def main():
    print("=== Antigravity CLI Health Check ===")
    
    # 1. Binary
    if os.path.exists(WRAPPER_BIN):
        ver = subprocess.run([WRAPPER_BIN, "--version"], capture_output=True, text=True)
        print(f"[✓] Binary installed: {ver.stdout.strip()}")
    else:
        print("[✗] Binary not found at /root/.local/bin/agy")
        sys.exit(1)

    # 2. Proxy Egress
    egress = get_proxy_egress()
    if "Failed" in egress:
        print(f"[!] SOCKS5 Egress: {egress} (Check socks5-japan.service)")
    else:
        print(f"[✓] Proxy Egress:  {egress}")

    # 3. Active Account
    email = get_current_email()
    if email:
        print(f"[✓] Active Token:  {email}")
    else:
        print("[!] No active token. Run python3 login.py")
        sys.exit(1)

    # 4. Live API Test
    print("[...] Testing live API response...")
    res = subprocess.run(
        [WRAPPER_BIN, "--dangerously-skip-permissions", "-p", "Reply with exactly: AGY_HEALTH_OK"],
        capture_output=True,
        text=True,
        timeout=30
    )
    if "AGY_HEALTH_OK" in res.stdout:
        print("[✓] Live API:      SUCCESS (Ready for operations)")
    else:
        print(f"[✗] Live API:      FAILED\n{res.stdout or res.stderr}")
        sys.exit(1)

if __name__ == "__main__":
    main()
