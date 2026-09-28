#!/bin/bash
# Full VPS provision and Antigravity CLI restore
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=========================================================="
echo "    Antigravity CLI Full Environment Restore & Setup      "
echo "=========================================================="

bash "$SCRIPT_DIR/setup.sh"

echo ""
echo "=========================================================="
echo "Setup complete! Available system commands:"
echo "  - agy          : Main Antigravity CLI"
echo "  - agy-login    : Unified 2-step verification login"
echo "  - agy-account  : Multi-account switcher and manager"
echo "  - agy-verify   : Quick health check and live API test"
echo "=========================================================="
