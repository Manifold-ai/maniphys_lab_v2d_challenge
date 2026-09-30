#!/usr/bin/env bash
# 截断复现的一条（训练机上，放在 tmux 里）：后台起看守，跑单行队列，等看守退出。计划 agent-doc/plan-ep1-ep7-divergence-2026-09-30.md 附录 A.4。
# 看守：连续 2 份完整 checkpoint 含非有限参数 → fc_stop（发散）；写出 <停止步数> 及以后的 checkpoint → fc_stop（截断）。
# fc_queue 遇到被停的 run 返回非零、停下；这里照常返回 0，让外层接着跑下一条。
# 用法：stages/policy/diag_truncated.sh <单行队列文件> <run 名> <停止步数> <标签>
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd -P)"; cd "$ROOT"
Q=${1:?}; RUN=${2:?}; STOP=${3:?}; TAG=${4:?}
[ "$(grep -cvE '^\s*(#|$)' "$Q")" = 1 ] || { echo "diag_truncated: $Q 必须只有一行"; exit 2; }
grep -q " $RUN " "$Q" || { echo "diag_truncated: $Q 里没有 $RUN"; exit 2; }
mkdir -p runs/logs
python3 stages/policy/ckpt_nonfinite.py --watch "$RUN" --stop-at-step "$STOP" --stop-after 2 --interval 60 --timeout 10800 \
  --tag "$TAG" > "runs/logs/$RUN.watch.log" 2>&1 &
W=$!
stages/policy/fc_queue.sh "$Q"; echo "=== fc_queue 退出码 $? ==="
# run 结束后看守会看到 DONE / STOP 自己退出；最多再等 5 分钟
for _ in $(seq 1 30); do kill -0 "$W" 2>/dev/null || break; sleep 10; done
kill "$W" 2>/dev/null; tail -2 "runs/logs/$RUN.watch.log"
exit 0
