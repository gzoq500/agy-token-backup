#!/bin/bash
if [ -z "$1" ]; then
  echo "Usage: $0 <code>"
  exit 1
fi
printf '%s' "$1" > /tmp/agy-code.txt
echo "Code written to /tmp/agy-code.txt"
