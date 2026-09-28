#!/usr/bin/env bash
# Day 1b（在 ml40 上执行，放 tmux，不依赖 Mac 在线）：满配 snack_box 训练 → 4096 世界评测 → 输入清单。
# 计划与事先登记的判据见 agent-doc/plan-day1b-2026-09-27.md。
# 用法（仓库根）：tmux new-session -d -s v2d-day1b stages/policy/queues/ml40_day1b.sh
# 日志 runs/logs/ml40_day1b.log，最后一行 DAY1B_DONE 或 DAY1B_FAILED；训练本身另有 runs/logs/<run>.* 与 run_record.jsonl。
# 中途失败后重跑同一条命令：fc_queue 从断点续训，已有评测 JSON 时 fc_eval 只打印摘要。
set -euo pipefail
cd "$(dirname "$0")/../../.."
mkdir -p runs/logs
exec >> runs/logs/ml40_day1b.log 2>&1
trap 'echo "=== $(date "+%F %T %Z") DAY1B_FAILED (line $LINENO)"' ERR
RUN=ctrl-snackbox-w2048-cap10m-ml40
echo "=== $(date '+%F %T %Z') start, source $(cat .v2d-source-commit 2>/dev/null || echo unknown)"
stages/policy/fc_queue.sh stages/policy/queues/ml40_day1b.txt
scripts/dev/record "day1/eval_$RUN" stages/policy/fc_eval.sh "$RUN" 349999104
scripts/dev/record "day1/policy_inputs_${RUN}_on_ml40" python3 stages/policy/policy_inputs.py "runs/flash_chord/$RUN/policy_349999104.safetensors"
echo "=== $(date '+%F %T %Z') DAY1B_DONE"
