#!/usr/bin/env bash
# 评一份没训完的 checkpoint（ep7 方盒两条 run 发散前最后一份有限的 policy），有坏世界就接着跑取证 rollout。
# 训练机上、仓库根执行，放 tmux。计划 agent-doc/plan-ep7-eval-and-guards-2026-10-02.md 的 A 部分。
# 用法：V2D_EVAL_SRC=<8c778f9 副本> V2D_ROLLOUT_SRC=<v0.4.0 + #185 副本> [V2D_WAIT_FOR_LOG=<日志> V2D_WAIT_FOR_RE=<结束行正则>] \
#         stages/evaluate/ep7_ckpt_eval.sh <run> <步数> <日志名>
#       V2D_EP7_EVAL_DRYRUN=1：只做第 0 步的检查并打印将要执行的命令，不写日志、不占 GPU。
# 0. 拒绝（退出码 2，不写日志）：日志 runs/logs/<日志名>.log 已存在；policy 文件不在；两份源码副本缺 SOURCE_V2D.txt；
#    这份 policy 含非有限参数（规矩一：含 NaN 的 policy 不评、不导出，ckpt_nonfinite.py --fail-on-nonfinite）。
# 1. 写长链标记 runs/.chain-active-<日志名>。设了 V2D_WAIT_FOR_LOG：等它的最后一行匹配 V2D_WAIT_FOR_RE（等别的链跑完）。
#    本日志里不出现别的链的结束标记原文（抄进来的行把标记换成中文）。
# 2. GPU 上有进程就每分钟看一次，最多等 V2D_GPU_WAIT_S 秒（默认 7200），等不到就停。
# 3. 评测：V2D_FC_SRC=<8c778f9 副本> stages/policy/fc_eval.sh <run> <步数>（4096 世界，与方盒评测链同一运行时），经 record 落成
#    results/day2/eval_<run>_s<步数>.txt（与评测链同名同处，batch_verdict.py 配同目录的不动基线就能判）。
# 4. 评测失败，或评测 JSON 里 non_finite_worlds 非空：再等一次 GPU，用 <v0.4.0 + #185 副本> 跑 stages/evaluate/blowup_rollout.py
#    （4096 世界，逐步抄物体与手掌位置，不清零）→ runs/ep7/<run>/blowup_s<步数>_w4096.npz。评测成功且没有非有限世界就不跑。
# 5. 日志最后一行 EP7_EVAL_DONE（评测 成功|失败；非有限世界 N 个|未知；取证 没跑|完成|失败）；停在第 1、2 步是 EP7_EVAL_FAILED。
set -uo pipefail
cd "$(dirname "$0")/../.."
RUN=${1:?用法见文件头}; STEP=${2:?用法见文件头}; NAME=${3:?用法见文件头}
EVAL_SRC=${V2D_EVAL_SRC:?要给 V2D_EVAL_SRC（8c778f9 副本）}; ROLLOUT_SRC=${V2D_ROLLOUT_SRC:?要给 V2D_ROLLOUT_SRC（v0.4.0 + #185 副本）}
LOG="runs/logs/$NAME.log"; MARK="runs/.chain-active-$NAME"; GPU_WAIT_S="${V2D_GPU_WAIT_S:-7200}"
P="runs/flash_chord/$RUN/policy_$STEP.safetensors"; E="runs/flash_chord/$RUN/eval_${STEP}_w4096.json"; D="runs/ep7/$RUN"
die() { echo "ep7_ckpt_eval: $*" >&2; exit 2; }
[[ $RUN =~ ^t[12]-ep[0-9]+-[a-z0-9_-]+$ && $STEP =~ ^[0-9]+$ && $NAME =~ ^[a-z0-9_]+$ ]] || die "参数不对：$RUN $STEP $NAME"
[[ $GPU_WAIT_S =~ ^[0-9]+$ ]] || die "V2D_GPU_WAIT_S 必须是非负整数"
[ ! -e "$LOG" ] || die "$LOG 已存在，拒绝（确认后改名或删掉再起）"
[ -f "$P" ] || die "没有 $P"
for s in "$EVAL_SRC" "$ROLLOUT_SRC"; do [ -f "$s/SOURCE_V2D.txt" ] && [ -d "$s/src/flash_chord" ] || die "$s 不是源码副本（缺 SOURCE_V2D.txt）"; done
if [ -n "${V2D_WAIT_FOR_LOG:-}" ]; then
  [ -f "$V2D_WAIT_FOR_LOG" ] || die "要等的日志 $V2D_WAIT_FOR_LOG 不存在"
  [ -n "${V2D_WAIT_FOR_RE:-}" ] || die "设了 V2D_WAIT_FOR_LOG 就要给 V2D_WAIT_FOR_RE"
fi
python3 stages/policy/ckpt_nonfinite.py --steps "$STEP" --fail-on-nonfinite "$RUN" > /dev/null || die "policy_$STEP 含非有限参数或读不了，不评"
EVAL_CMD=(scripts/dev/record "day2/eval_${RUN}_s${STEP}" stages/policy/fc_eval.sh "$RUN" "$STEP")
ROLL_CMD="cd /workspace && python /repo/stages/evaluate/blowup_rollout.py /repo/$P /repo/$D/blowup_s${STEP}_w4096 --worlds 4096"
if [ "${V2D_EP7_EVAL_DRYRUN:-0}" = 1 ]; then
  echo "DRYRUN ${NAME}：policy $P 有限；评测运行时 $(head -1 "$EVAL_SRC/SOURCE_V2D.txt")；取证运行时 $(head -1 "$ROLLOUT_SRC/SOURCE_V2D.txt")"
  echo "DRYRUN 等：${V2D_WAIT_FOR_LOG:-（不等别的链）} ${V2D_WAIT_FOR_RE:-}；GPU 最多等 ${GPU_WAIT_S} 秒"
  echo "DRYRUN 评测：V2D_FC_SRC=$EVAL_SRC ${EVAL_CMD[*]}  → ${E}（已存在：$([ -s "$E" ] && echo 是 || echo 否)）"
  echo "DRYRUN 取证（评测失败或有非有限世界才跑）：V2D_FC_SRC=$ROLLOUT_SRC in-flash-chord \"$ROLL_CMD\""
  echo "EP7_EVAL_DRYRUN_OK"; exit 0
fi
mkdir -p runs/logs "$D" results/ep7 results/day2
touch "$MARK"; trap 'rm -f "$MARK"' EXIT
say() { echo "=== $(date '+%F %T %Z') $*" | tee -a "$LOG"; }
stop() { say "$*"; say "EP7_EVAL_FAILED"; exit 1; }
demark() { sed -E 's/EXPORT_CHAIN_(DONE|FAILED)/导出链结束/g; s/DAY2_(EVAL|TRAIN)_(DONE|FAILED)/上一段链结束/g; s/DIAG2_(DONE|FAILED)/诊断链结束/g; s/EP7_EVAL_(DONE|FAILED)/评测链结束/g'; }
gpu_pids() { nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null | tr -d ' ' | paste -sd, -; }
wait_gpu() {
  local t0=$SECONDS
  [ -z "$(gpu_pids)" ] && return 0
  say "GPU 上有别的进程（$(gpu_pids)），每 ${V2D_POLL_S:-60} 秒看一次"
  while [ -n "$(gpu_pids)" ]; do
    [ $((SECONDS - t0)) -lt "$GPU_WAIT_S" ] || stop "GPU 被别的进程占了 ${GPU_WAIT_S} 秒，停下"
    sleep "${V2D_POLL_S:-60}"
  done
  say "GPU 空了"
}
say "start ${NAME}：${RUN} policy_${STEP}，评测运行时 $(head -1 "$EVAL_SRC/SOURCE_V2D.txt")，来历 $(cat .v2d-source-commit 2>/dev/null || echo unknown)"
if [ -n "${V2D_WAIT_FOR_LOG:-}" ]; then
  say "等 $V2D_WAIT_FOR_LOG 结束（它的最后一行匹配给定的结束行正则）"
  until grep -qE "$V2D_WAIT_FOR_RE" < <(tail -1 "$V2D_WAIT_FOR_LOG" 2>/dev/null); do sleep "${V2D_POLL_S:-60}"; done
  say "上一段已结束：$(tail -1 "$V2D_WAIT_FOR_LOG" | demark)"
fi
wait_gpu
say "评测 ${RUN} policy_${STEP}（4096 世界）"
eval_state=成功
V2D_FC_SRC="$EVAL_SRC" "${EVAL_CMD[@]}" >> "$LOG" 2>&1 < /dev/null || eval_state=失败
nf=未知
if [ "$eval_state" = 成功 ] && [ -s "$E" ]; then
  nf="$(python3 -c 'import json,sys; print(len(json.load(open(sys.argv[1])).get("non_finite_worlds", [])))' "$E" 2>/dev/null || echo 未知)"
fi
say "评测${eval_state}；非有限世界 ${nf}$([ "$nf" = 未知 ] || echo ' 个')"
roll_state=没跑
if [ "$eval_state" = 失败 ] || [ "$nf" != 0 ]; then
  wait_gpu
  say "取证 rollout（4096 世界，物体与手掌位置原样存）"
  if V2D_FC_SRC="$ROLLOUT_SRC" V2D_GPU=1 V2D_CONTAINER_NAME="ep7-blowup-$RUN" scripts/dev/record "ep7/blowup_${RUN}_s${STEP}" \
       scripts/dev/in-flash-chord "$ROLL_CMD" >> "$LOG" 2>&1 < /dev/null; then
    roll_state=完成
  else
    roll_state=失败
  fi
  rm -rf "$D/blowup_s${STEP}_w4096_hydra"
fi
say "EP7_EVAL_DONE（评测 ${eval_state}；非有限世界 ${nf}；取证 ${roll_state}）"
