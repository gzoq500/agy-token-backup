#!/usr/bin/env python3
"""
patch_binary.py - Dynamic patcher for Antigravity CLI binary.
Bypasses Google Borg's internal fail-fast CPUID feature checks (go/sigill-fail-fast),
specifically the pclmulqdq / AVX-512 check in .preinit_array that causes SIGILL crashes
on virtualized processors (QEMU/KVM Virtual CPU 2.5+, older Xeon/EPYC VPS).
"""

import sys
import os
import struct

def patch_antigravity_binary(binary_path):
    if not os.path.exists(binary_path):
        print(f"[ERROR] Binary not found: {binary_path}", file=sys.stderr)
        return False

    with open(binary_path, "rb") as f:
        data = bytearray(f.read())

    # Check for the fail-fast error string
    str_target = b"FATAL ERROR: This binary was compiled with pclmul enabled"
    if str_target not in data:
        print("[INFO] pclmul fail-fast string not found; binary may already be compatible.")
        return True

    # Parse 64-bit ELF header
    if data[:4] != b"\x7fELF":
        print("[ERROR] Not a valid ELF binary.", file=sys.stderr)
        return False

    e_shoff = struct.unpack_from("<Q", data, 40)[0]
    e_shentsize = struct.unpack_from("<H", data, 58)[0]
    e_shnum = struct.unpack_from("<H", data, 60)[0]
    e_shstrndx = struct.unpack_from("<H", data, 62)[0]

    if e_shoff == 0 or e_shnum == 0:
        print("[ERROR] Section header table not found.", file=sys.stderr)
        return False

    shstr_hdr = e_shoff + e_shstrndx * e_shentsize
    shstr_offset = struct.unpack_from("<Q", data, shstr_hdr + 24)[0]

    preinit_addr = None
    for i in range(e_shnum):
        hdr = e_shoff + i * e_shentsize
        name_idx = struct.unpack_from("<I", data, hdr)[0]
        sh_type = struct.unpack_from("<I", data, hdr + 4)[0]
        name = data[shstr_offset + name_idx:].split(b"\x00")[0].decode("ascii", "ignore")
        if name == ".preinit_array" or sh_type == 16:  # SHT_PREINIT_ARRAY = 16
            preinit_addr = struct.unpack_from("<Q", data, hdr + 16)[0]
            break

    if not preinit_addr:
        print("[ERROR] .preinit_array section not found.", file=sys.stderr)
        return False

    # Find relocation targeting .preinit_array[0]
    # In x86_64 ELF: Elf64_Rela has (r_offset, r_info, r_addend)
    func_offset = None
    for i in range(0, len(data) - 24, 8):
        r_offset, r_info, r_addend = struct.unpack_from("<QQq", data, i)
        if r_offset == preinit_addr and (r_info & 0xffffffff) == 8:  # R_X86_64_RELATIVE = 8
            func_offset = r_addend  # Virtual address == file offset in primary LOAD segment
            break

    if func_offset is None or func_offset >= len(data):
        print("[ERROR] Could not resolve relocation for CPU check function.", file=sys.stderr)
        return False

    old_byte = data[func_offset]
    if old_byte == 0xc3:
        print(f"[OK] Binary already patched at offset 0x{func_offset:x} (RET 0xc3).")
        return True

    # Patch with RET (0xc3)
    data[func_offset] = 0xc3
    with open(binary_path, "wb") as f:
        f.write(data)

    print(f"[SUCCESS] Patched CPU check function at 0x{func_offset:x} from 0x{old_byte:02x} to 0xc3 (RET).")
    return True

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "/root/.local/bin/agy-real"
    success = patch_antigravity_binary(target)
    sys.exit(0 if success else 1)
