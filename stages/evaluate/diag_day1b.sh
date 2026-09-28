#!/usr/bin/env bash
# Day 1b 逐帧诊断（在 mf4090 上执行，占 GPU；计划见 agent-doc/plan-day1b-2026-09-27.md 第 2 版）。
# 对每个 policy：先跑原样的 fc_eval.sh（4096 世界），再跑 diag_rollout.py（同卡、同世界数，只多包一层、存下 rollout），
# 然后 diag_report.py 出报告（七道闸，任何一道不过退出码 3，整条链停下）。
# 每个 run 目录里要有 policy_349999104.safetensors 与另一张卡上的参照评测 eval_349999104_w4096.ml40.json（从 ml40 拷来）。
# 输出：runs/diag/<run>/rollout_w<世界数>.{npz,json}；results/day1/diag_<run>.txt（经 record）与 .svg。
# 用法（仓库根，后台，不依赖 Mac 在线）：setsid nohup stages/evaluate/diag_day1b.sh > runs/logs/diag_day1b.log 2>&1 < /dev/null &
# 日志最后一行 DIAG_DONE 或 DIAG_FAILED。V2D_EVAL_WORLDS 默认 4096（4090 装不下时改 1024，并在报告里注明）。
set -euo pipefail
cd "$(dirname "$0")/../.."
trap 'echo "=== $(date "+%F %T %Z") DIAG_FAILED (line $LINENO)"' ERR
WORLDS=${V2D_EVAL_WORLDS:-4096}
say() { echo "=== $(date '+%F %T %Z') $*"; }
say "start, source $(cat .v2d-source-commit 2>/dev/null || echo unknown), upstream $(git -C third_party/video_to_data rev-parse --short=7 HEAD), worlds $WORLDS"
others="$(nvidia-smi --query-compute-apps=pid --format=csv,noheader | tr -d ' ')"
[ -z "$others" ] || { say "GPU 上有别的进程（$others），不跑"; false; }
# run 名 | 分段（关注段首末帧）| 参考的已知答案（增量 > 0.5° 的首末帧、首次超过 1.5 rad 的帧，来自 static_baseline_*.txt）| 事先预测
while read -r run seg0 seg1 m0 m1 g pred; do
  O=runs/flash_chord/$run; D=runs/diag/$run; mkdir -p "$D" results/day1
  P=$O/policy_349999104.safetensors; X=$O/eval_349999104_w4096.ml40.json
  [ -f "$P" ] && [ -f "$X" ] || { say "$O 缺 policy 或 ml40 参照评测"; false; }
  say "$run：原样 fc_eval.sh（$WORLDS 世界）"
  V2D_EVAL_WORLDS=$WORLDS stages/policy/fc_eval.sh "$run" 349999104
  say "$run：diag_rollout.py（$WORLDS 世界）"
  V2D_GPU=1 V2D_CONTAINER_NAME="diag-$run" scripts/dev/in-flash-chord \
    "cd /workspace && python /repo/stages/evaluate/diag_rollout.py /repo/$P /repo/$D/rollout_w$WORLDS --worlds $WORLDS"
  say "$run：报告"
  PRED=(); [ "$pred" = - ] || PRED=(--predict ${pred/:/ })
  scripts/dev/record "day1/diag_$run" scripts/dev/in-flash-chord \
    "python /repo/stages/evaluate/diag_report.py /repo/$D/rollout_w$WORLDS.npz --diag-json /repo/$D/rollout_w$WORLDS.json --same-card-json /repo/$O/eval_349999104_w$WORLDS.json --cross-card-json /repo/$X --segments $seg0 $seg1 --expect-ref $m0 $m1 $g ${PRED[*]} --svg /repo/results/day1/diag_$run.svg --title '$run（$WORLDS 世界）'"
done <<'RUNS'
t1-ep20-w2048-cap10m-ml40 209 420 209 420 269 359:94
t1-ep20-w2048-cap1m-mf4090 209 420 209 420 269 -
ctrl-snackbox-w2048-cap1m-mf4090 446 704 446 704 504 -
RUNS
say DIAG_DONE
