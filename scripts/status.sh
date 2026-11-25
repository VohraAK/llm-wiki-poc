#!/bin/bash
# Overnight status: last 10 lines of overnight.log and all bundle commits.
cd "$(dirname "$0")/.." || exit 1
echo "=== $(date '+%F %T') ==="
echo; echo "--- runs/overnight.log (last 10) ---"
tail -n 10 runs/overnight.log
echo; echo "--- wiki/bundle commits ---"
git -C wiki/bundle log --format='%h %ad %s' --date=format:'%H:%M'
