#!/usr/bin/env bash
set -euo pipefail

file=${1:?Usage: $0 <file> <threshold>}
threshold=${2:?Usage: $0 <file> <threshold>}

grep -oP ',[[:space:]]*\K[^,}]+(?=[[:space:]]*\})' "$file" \
  | sed -E 's/^[[:space:]]+//; s/[[:space:]]+$//' \
  | awk -v t="$threshold" '$1+0 > t+0'
