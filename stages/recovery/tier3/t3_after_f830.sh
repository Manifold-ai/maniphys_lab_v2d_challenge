#!/usr/bin/env bash
# One-off follow-up (2026-10-10): wait for the focal-830 + floor batch (logs/t3_world_all_f830.log) to finish, then run
# the floor acceptance check on the new parquet and on the two earlier versions, and write one result file:
#   runs/floor/acceptance_f830.txt
# Detached from any session: setsid nohup t3_after_f830.sh > /dev/null 2>&1 < /dev/null &
set -u
S=$(cd "$(dirname "$0")" && pwd)
T=${T3_ROOT:-/lab_data/yqchen/v2d/tier3}
PY=${T3_PY:-/lab_data/yqchen/v2d/venv/bin/python}
LOG=$T/logs/t3_world_all_f830.log
OUTF=$T/runs/floor/acceptance_f830.txt
until grep -q "ALLDONE\|FAILED" "$LOG" 2>/dev/null; do sleep 60; done
{
  echo "# floor acceptance $(date '+%F %T') ; batch log: $LOG ; deployed: $(cat "$T/code/DEPLOYED")"
  echo "## batch"
  cat "$LOG"
  for v in tier3_cari4d_f830_floor tier3_cari4d_floor tier3_cari4d; do
    echo "## $v (+ ${v}_suspect)"
    "$PY" "$S/t3_floor_check.py" "$T" "$T/runs/$v" "$T/runs/${v}_suspect" 2>&1 | grep -v -i warn
  done
  echo "## counts"
  for v in tier3_cari4d_f830_floor tier3_cari4d_f830_floor_suspect; do echo "$v $(ls "$T/runs/$v/data/chunk-000" 2>/dev/null | wc -l)"; done
  echo "DONE"
} > "$OUTF" 2>&1
