#!/usr/bin/env bash
set -uo pipefail
OUT=$HOME/laguna_soak_out
export SOAK_HOURS=12
export LAGUNA_ENDPOINT=http://localhost:8000/v1
export PYTHONUNBUFFERED=1
cd "$OUT" || exit 1
echo "SOAK_WRAPPER_START $(date -Is)" >> logs/wrapper.log
python3 -u soak_driver.py >> logs/driver_stdout.log 2>&1
EC=$?
echo "SOAK_DRIVER_EXIT=$EC $(date -Is)" >> logs/wrapper.log
python3 -u score_and_restore.py >> logs/score_restore_stdout.log 2>&1
echo "SCORE_RESTORE_DONE $(date -Is)" >> logs/wrapper.log
LC_OUT=<CONTROL_PLANE>/laguna_soak_out
mkdir -p "$LC_OUT"
cp -a LAGUNA_SOAK_12H_20260725.md part0_inventory.md "$LC_OUT/" 2>/dev/null || true
cp -a logs/*.jsonl probes/*.jsonl progress/* "$LC_OUT/" 2>/dev/null || true
echo "ALL_DONE $(date -Is)" >> logs/wrapper.log
