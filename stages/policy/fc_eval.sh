#!/usr/bin/env bash
# 用 FlashCHORD 自带评测器（scripts/evaluate_policy.py）评测一个 run 的 policy（训练机上执行）。
# 环境由 checkpoint 自带的配置重建（use_checkpoint_config），评测配置用官方默认（deterministic、start_frame 0）。
# 用法：stages/policy/fc_eval.sh <run> [步数]      默认评测步数最大的 policy_N
#       V2D_EVAL_WORLDS=4096（默认，官方值）；V2D_ALLOW_SHARED_GPU=1 可在 GPU 有别的进程时强行评测
# 输出：runs/flash_chord/<run>/eval_<步数>_w<世界数>.json；日志 runs/logs/<run>.eval_<步数>_w<世界数>.log
# 已有结果就直接打印，不重复评测。
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd -P)"; cd "$ROOT"
die() { echo "fc_eval: $*" >&2; exit "${2:-2}"; }
RUN=${1:?用法：fc_eval.sh <run> [步数]}; STEP=${2:-}; WORLDS=${V2D_EVAL_WORLDS:-4096}
[[ $RUN =~ ^[a-z0-9][a-z0-9_-]{2,59}$ ]] || die "run 名非法：$RUN"
[[ $WORLDS =~ ^[1-9][0-9]*$ ]] || die "V2D_EVAL_WORLDS 必须是正整数"
O="runs/flash_chord/$RUN"; [ -d "$O" ] || die "没有 $O"
if [ -z "$STEP" ]; then
  STEP="$(ls "$O"/policy_*.safetensors 2>/dev/null | sed -E 's/.*policy_([0-9]+)\.safetensors/\1/' | sort -n | tail -1)"
fi
[[ $STEP =~ ^[0-9]+$ ]] || die "$O 里没有 policy_*.safetensors"
P="$O/policy_${STEP}.safetensors"; [ -f "$P" ] || die "没有 $P"
OUTJ="$O/eval_${STEP}_w${WORLDS}.json"; LOG="runs/logs/$RUN.eval_${STEP}_w${WORLDS}.log"
summary() {
  python3 - "$OUTJ" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
m = d.get("metrics", d)
keys = ["evaluation/add_auc", "evaluation/chord_sr", "evaluation/maniptrans_sr", "evaluation/spider_sr_uncentered",
        "evaluation/mppe_cm", "evaluation/spider_position_error_centered_m", "evaluation/world_count"]
for k in keys:
    if k in m:
        print(f"  {k:<48} {m[k]}")
PY
}
if [ -s "$OUTJ" ]; then echo "fc_eval: 已有结果 $OUTJ"; summary; exit 0; fi
exec 9>"$O/.eval.lock"; flock -n 9 || die "$O 正在被另一个 fc_eval 评测"
others="$(nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null | tr -d ' ')"
[ -z "$others" ] || [ "${V2D_ALLOW_SHARED_GPU:-0}" = 1 ] || die "GPU 上有别的进程（PID ${others//$'\n'/,}），拒绝评测" 6
mkdir -p runs/logs
echo "=== $(date '+%F %T %Z') fc_eval $RUN policy_$STEP world_count=$WORLDS ===" >> "$LOG"
V2D_GPU=1 V2D_CONTAINER_NAME="fc-eval-$RUN" scripts/dev/in-flash-chord \
  "cd /workspace && python scripts/evaluate_policy.py $(printf '%q ' "evaluation.checkpoint=/repo/$P" \
   "evaluation.world_count=$WORLDS" "evaluation.metrics_output=/repo/$OUTJ" "hydra.run.dir=/repo/$O/hydra/eval-$STEP-w$WORLDS")" \
  >> "$LOG" 2>&1 9>&-
rc=$?
[ "$rc" = 0 ] && [ -s "$OUTJ" ] || die "评测失败（退出码 $rc），见 $LOG"
echo "fc_eval: $RUN policy_$STEP（$WORLDS 世界）→ $OUTJ"; summary
