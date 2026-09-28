# Antigravity CLI VPS Provisioner & Multi-Account Manager

Automated setup, CPU feature patching, SOCKS5 proxy routing, and seamless 2-step verification authentication for running Google Antigravity CLI (`agy`) on headless Linux VPS environments.

---

## Solved Obstacles

1. **CPU `pclmulqdq` Fail-Fast Crash (`go/sigill-fail-fast`)**:
   - Modern `agy` binaries are compiled with strict pre-initialization checks (`.preinit_array`) that abort with `SIGILL` on virtualized processors (QEMU/KVM Virtual CPU 2.5+, older Xeon/EPYC VPS).
   - `patch_binary.py` dynamically parses the ELF section headers, resolves the `.preinit_array` relocation entry, and patches the check function with `RET (0xc3)`.
   - The binary is locked with `chattr +i` to block corrupting background self-updates.

2. **API Geographic Restriction (`User location is not supported`)**:
   - Egress from Hong Kong or restricted regions returns HTTP 400.
   - The included wrapper automatically routes all `agy` requests through a transparent SOCKS5 tunnel (`127.0.0.1:1080` in Japan/US).

3. **2-Step Verification Workflow (OAuth + Account Validation)**:
   - `login.py` runs a virtual PTY terminal to extract the Google OAuth authorization URL (Step 1).
   - After code injection, it automatically probes the API. If Google returns `Eligibility check failed / signin/continue` (VALIDATION_REQUIRED), it extracts the Step 2 browser verification link, pauses for completion, and validates the account.

---

## File Structure

```text
/root/agy-token-backup/
├── setup.sh           # Master 1-shot installer (deps, download, patch, wrapper)
├── patch_binary.py    # Standalone ELF CPUID fail-fast patcher
├── login.py           # Unified login manager with 2-step verification detection (agy-login)
├── account.py         # Multi-account manager & instant session switcher (agy-account)
├── verify.py          # Quick 4-point health check & live API test (agy-verify)
├── submit-code.sh     # Quick helper to write authorization code to /tmp/agy-code.txt
└── README.md          # Documentation
```

---

## Multi-Account Management (Ganti Akun)

All logged-in tokens are automatically preserved in `/root/.gemini/antigravity-cli/token-backups/<email>.oauth-token`.

### 1. Lihat Daftar Akun Tersimpan
```bash
agy-account list
```

### 2. Ganti Akun Aktif (Instan)
Cukup masukkan email atau nama depannya:
```bash
agy-account switch nakamotogox
# atau
agy-account switch lokeigox000@gmail.com
```
Perintah ini otomatis mengaktifkan token tersebut dan langsung memverifikasi koneksi ke API Google.

### 3. Tambah / Login Akun Baru
Jalankan login manager kapan saja:
```bash
agy-login
```
Token akun yang sedang aktif akan otomatis dicadangkan terlebih dahulu, kemudian akun baru diproses lewat flow 2-step verification.

---

## Quick Start Guide

### Step 1: Install & Patch Antigravity CLI
Run the provisioner on any fresh Ubuntu/Debian VPS:
```bash
bash /root/agy-token-backup/setup.sh
```

### Step 2: Log In & Verify Account
Execute the login manager:
```bash
python3 /root/agy-token-backup/login.py
```

1. **Step 1 (OAuth)**: Open the printed Google OAuth authorization link in your browser, log in with the target account, and paste the authorization code.
2. **Step 2 (Account Validation)**: If the account requires browser verification, `login.py` will display the `signin/continue` link. Open it in the same browser session, complete the check, and press Enter.

### Step 3: Health Check & Operations
Verify that the binary, proxy, and token are active:
```bash
python3 /root/agy-token-backup/verify.py
```

Run non-interactive queries directly:
```bash
agy --dangerously-skip-permissions -p "Ping test: balas Pong!"
```
