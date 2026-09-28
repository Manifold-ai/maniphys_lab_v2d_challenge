#!/usr/bin/env bash
# Day 1b：ep20 逐帧诊断（在 mf4090 上执行，占 GPU 几分钟；计划与事先登记见 agent-doc/plan-day1b-2026-09-27.md）。
# 两个 ep20 最终 policy（ml40 1000 万 buffer 为主，mf4090 100 万 buffer 作对照）各按官方评测路径跑 256 个世界并存下逐帧数据
# （diag_rollout.py），再逐个分析（diag_rotation.py）。每个 run 目录里要有 policy_349999104.safetensors 与参照评测
# eval_349999104_w4096.json（ml40 上 4096 世界的那份，从 ml40 拷来）。
# 输出：runs/diag/<run>/rollout_w256.{npz,json}；results/day1/diag_ep20_<run>.txt（经 record）与 .svg。
# 用法（仓库根，后台，不依赖 Mac 在线）：
#   setsid nohup stages/evaluate/diag_ep20_day1b.sh > runs/logs/diag_ep20.log 2>&1 < /dev/null &
# 日志最后一行 DIAG_DONE 或 DIAG_FAILED。
set -euo pipefail
cd "$(dirname "$0")/../.."
trap 'echo "=== $(date "+%F %T %Z") DIAG_FAILED (line $LINENO)"' ERR
echo "=== $(date '+%F %T %Z') start, source $(cat .v2d-source-commit 2>/dev/null || echo unknown)"
others="$(nvidia-smi --query-compute-apps=pid --format=csv,noheader | tr -d ' ')"
[ -z "$others" ] || { echo "GPU 上有别的进程（$others），不跑"; false; }
for run in t1-ep20-w2048-cap10m-ml40 t1-ep20-w2048-cap1m-mf4090; do
  O=runs/flash_chord/$run; D=runs/diag/$run; mkdir -p "$D" results/day1
  [ -f "$O/policy_349999104.safetensors" ] && [ -f "$O/eval_349999104_w4096.json" ] || { echo "$O 缺 policy 或参照评测"; false; }
  echo "=== $(date '+%F %T %Z') rollout $run（256 世界）"
  V2D_GPU=1 V2D_CONTAINER_NAME="diag-$run" scripts/dev/in-flash-chord \
    "python /repo/stages/evaluate/diag_rollout.py /repo/$O/policy_349999104.safetensors /repo/$D/rollout_w256 --worlds 256"
  echo "=== $(date '+%F %T %Z') 分析 $run"
  # 有效性不过时 diag_rotation 退出码 3：record 把输出存成 .failed、整条链停下，不做解读
  scripts/dev/record "day1/diag_ep20_$run" scripts/dev/in-flash-chord \
    "python /repo/stages/evaluate/diag_rotation.py /repo/$D/rollout_w256.npz /repo/$D/rollout_w256.json /repo/$O/eval_349999104_w4096.json --segment 209 420 --svg /repo/results/day1/diag_ep20_$run.svg --title '$run：ep20 逐帧诊断（256 世界）'"
done
echo "=== $(date '+%F %T %Z') DIAG_DONE"
