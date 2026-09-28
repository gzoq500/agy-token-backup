#!/usr/bin/env python3
"""
account.py - Antigravity Multi-Account Switcher & Session Manager.

Usage:
  python3 account.py list                     # List all saved accounts & active status
  python3 account.py switch <email_or_name>   # Switch active account instantly
  python3 account.py current                  # Show currently active email
  python3 account.py test                     # Test active account with live prompt
"""

import os
import sys
import json
import base64
import shutil
import subprocess

TOKEN_PATH = "/root/.gemini/antigravity-cli/antigravity-oauth-token"
BACKUP_DIR = "/root/.gemini/antigravity-cli/token-backups"
WRAPPER_BIN = "/root/.local/bin/agy"

def get_email_from_file(path):
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            d = json.load(f)
        id_token = d.get("id_token", "")
        if id_token and "." in id_token:
            p = id_token.split(".")[1]
            p += "=" * (-len(p) % 4)
            return json.loads(base64.urlsafe_b64decode(p)).get("email")
    except Exception:
        pass
    return None

def get_active_email():
    return get_email_from_file(TOKEN_PATH)

def list_accounts():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    active_email = get_active_email()
    files = [f for f in os.listdir(BACKUP_DIR) if f.endswith(".oauth-token")]
    
    print("========================================================================")
    print("                DAFTAR AKUN ANTIGRAVITY CLI TERSIMPAN                   ")
    print("========================================================================")
    
    if not files:
        print("Belum ada backup akun di", BACKUP_DIR)
        print("Gunakan 'python3 login.py' untuk menambahkan akun baru.")
        return

    for idx, fname in enumerate(sorted(files), 1):
        fpath = os.path.join(BACKUP_DIR, fname)
        email = get_email_from_file(fpath) or fname.replace(".oauth-token", "")
        is_active = (active_email and email == active_email)
        status_tag = " [AKTIF]" if is_active else ""
        mtime = os.path.getmtime(fpath)
        import datetime
        dt = datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
        print(f" {idx}. {email:<35} (diperbarui: {dt}){status_tag}")
    
    print("========================================================================")
    print("Perintah switch: python3 account.py switch <nama_atau_email>")

def switch_account(target):
    os.makedirs(BACKUP_DIR, exist_ok=True)
    files = [f for f in os.listdir(BACKUP_DIR) if f.endswith(".oauth-token")]
    
    match = None
    matched_email = None
    target_clean = target.lower().strip()
    
    for f in files:
        fpath = os.path.join(BACKUP_DIR, f)
        email = (get_email_from_file(fpath) or "").lower()
        fname_clean = f.lower()
        if target_clean in email or target_clean in fname_clean:
            match = fpath
            matched_email = email or f
            break
            
    if not match:
        print(f"[ERROR] Akun '{target}' tidak ditemukan di {BACKUP_DIR}.", file=sys.stderr)
        print("Ketik 'python3 account.py list' untuk melihat daftar akun yang tersimpan.")
        sys.exit(1)

    # Backup current active token first if exists
    current_email = get_active_email()
    if current_email and os.path.exists(TOKEN_PATH):
        clean_cur = current_email.replace("@", "_at_")
        cur_backup = os.path.join(BACKUP_DIR, f"{clean_cur}.oauth-token")
        shutil.copy2(TOKEN_PATH, cur_backup)

    # Overwrite active token with matched target
    shutil.copy2(match, TOKEN_PATH)
    print(f"[✓] Akun berhasil diganti ke: {matched_email}")
    
    # Run instant live test
    print("[...] Menguji token baru ke API Google...")
    res = subprocess.run(
        [WRAPPER_BIN, "--dangerously-skip-permissions", "-p", "Reply with: AGY_SWITCH_OK"],
        capture_output=True,
        text=True,
        timeout=35
    )
    if "AGY_SWITCH_OK" in res.stdout:
        print("[✓] Status API: AKTIF & VALID. Siap digunakan!")
    elif "signin/continue" in res.stdout or "Eligibility check failed" in res.stdout:
        print("[!] Akun ini membutuhkan verifikasi browser (Step 2). Jalankan 'python3 login.py' untuk menyelesaikan.")
    else:
        print(f"[!] Respons API:\n{res.stdout or res.stderr}")

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("list", "-l", "--list"):
        list_accounts()
    elif sys.argv[1] in ("current", "-c"):
        cur = get_active_email()
        print(f"Akun aktif saat ini: {cur or 'Tidak ada token aktif'}")
    elif sys.argv[1] in ("switch", "-s"):
        if len(sys.argv) < 3:
            print("Gunakan: python3 account.py switch <email_atau_nama>")
            sys.exit(1)
        switch_account(sys.argv[2])
    elif sys.argv[1] in ("test", "-t"):
        subprocess.run(["python3", "/root/agy-token-backup/verify.py"])
    else:
        # Default fallback: try to switch directly if argument looks like email or query
        switch_account(sys.argv[1])

if __name__ == "__main__":
    main()
