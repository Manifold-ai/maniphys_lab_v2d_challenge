#!/usr/bin/env bash
# Day 1b 逐帧诊断（在 mf4090 上执行，占 GPU；计划见 agent-doc/plan-day1b-2026-09-27.md 第 3 版）。
# 对运行表里的每个 policy：原样 fc_eval.sh → diag_rollout.py（同卡、同世界数，只多包一层、存下 rollout）→ diag_report.py（经 record）。
# 同卡比对要求本机评测 JSON 确实是本机算的：评测前已存在的 eval JSON 必须有本机的 fc_eval 日志；ml40 参照评测核对 sha256。
# 某个 policy 的报告闸没过（diag_report 退出码 3）：记下、继续下一个，最后汇总；其他错误立刻停。
# 用法（仓库根，后台）：setsid nohup stages/evaluate/diag_day1b.sh stages/evaluate/diag_day1b.runs > runs/logs/diag_day1b.log 2>&1 < /dev/null &
#   试跑：V2D_EVAL_WORLDS=256 V2D_DIAG_RECORD_DIR=tests stages/evaluate/diag_day1b.sh stages/evaluate/diag_dryrun.runs
# 运行表可选第 10 列：Q1 关键帧的换算倍数（diag_report.py --frame-scale），缺省 1；真实时长回放的 run 给 1.6666667。
# 日志最后一行 DIAG_DONE、DIAG_GATES_FAILED（有闸没过）或 DIAG_FAILED（出错）。
set -Eeuo pipefail
cd "$(dirname "$0")/../.."
say() { echo "=== $(date '+%F %T %Z') $*"; }
fail() { say "$*"; say DIAG_FAILED; exit 1; }
trap 'say "DIAG_FAILED（第 $LINENO 行命令失败）"' ERR
TABLE=${1:?用法：diag_day1b.sh <运行表>}; WORLDS=${V2D_EVAL_WORLDS:-4096}; RD=${V2D_DIAG_RECORD_DIR:-day1}
say "start, table $TABLE, worlds $WORLDS, source $(cat .v2d-source-commit 2>/dev/null || echo unknown), upstream $(git -C third_party/video_to_data rev-parse --short=7 HEAD)"
others="$(nvidia-smi --query-compute-apps=pid --format=csv,noheader | tr -d ' ')"
[ -z "$others" ] || fail "GPU 上有别的进程（$others），不跑"
gate_failed=0
while read -r run step seg0 seg1 m0 m1 g pf refsha scale; do
  case "$run" in ''|'#'*) continue ;; esac
  O=runs/flash_chord/$run; D=runs/diag/$run; P=$O/policy_$step.safetensors
  E=$O/eval_${step}_w$WORLDS.json; X=$O/eval_${step}_w4096.ml40.json
  mkdir -p "$D" "results/$RD"
  [ -f "$P" ] || fail "缺 $P"
  CROSS=()
  if [ "$refsha" != - ]; then
    [ "$(sha256sum "$X" | cut -c1-16)" = "$refsha" ] || fail "$X 的 sha256 与运行表不符"
    CROSS=(--cross-card-json "/repo/$X")
  fi
  if [ -f "$E" ] && [ ! -f "runs/logs/$run.eval_${step}_w$WORLDS.log" ]; then
    fail "$E 已存在却没有本机的 fc_eval 日志：它可能不是本机算的，同卡比对不成立"
  fi
  say "$run：原样 fc_eval.sh（$WORLDS 世界）"
  V2D_EVAL_WORLDS=$WORLDS stages/policy/fc_eval.sh "$run" "$step"
  say "$run：diag_rollout.py（$WORLDS 世界）"
  V2D_GPU=1 V2D_CONTAINER_NAME="diag-$run" scripts/dev/in-flash-chord \
    "cd /workspace && python /repo/stages/evaluate/diag_rollout.py /repo/$P /repo/$D/rollout_w$WORLDS --worlds $WORLDS"
  say "$run：报告"
  PRED=(); [ "$pf" = - ] || PRED=(--predict-frame "$pf")
  [ -n "${scale:-}" ] && PRED+=(--frame-scale "$scale")
  if scripts/dev/record "$RD/diag_$run" scripts/dev/in-flash-chord \
      "python /repo/stages/evaluate/diag_report.py /repo/$D/rollout_w$WORLDS.npz --diag-json /repo/$D/rollout_w$WORLDS.json --same-card-json /repo/$E ${CROSS[*]} --segments $seg0 $seg1 --expect-ref $m0 $m1 $g ${PRED[*]} --svg /repo/results/$RD/diag_$run.svg --title '$run（$WORLDS 世界）'"; then
    say "$run：报告完成，闸全过"
  else
    rc=$?
    [ "$rc" = 3 ] || fail "$run：报告出错（退出码 $rc）"
    gate_failed=$((gate_failed + 1)); say "$run：有闸没过，报告存为 results/$RD/diag_$run.txt.failed，继续下一个"
  fi
done < "$TABLE"
if [ "$gate_failed" = 0 ]; then say DIAG_DONE; else say "DIAG_GATES_FAILED（$gate_failed 个 policy 的闸没过）"; exit 3; fi
