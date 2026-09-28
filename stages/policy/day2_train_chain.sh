#!/usr/bin/env bash
# Day 2 训练链（计划 agent-doc/plan-day2-2026-09-28.md 第 2 版）：按期望表逐条冒烟、再逐条正式训练；单条失败不连累其余。训练机上执行，放 tmux。
#   0. 来历：开头记下 .v2d-source-commit，每条 run 前比对，变了就停整条链（同步会改写它、也会换掉链后面才调用的脚本）；GPU 上有别的进程就停
#   1. 正向核对：期望表里每条 run（冒烟与正式）的展开配置（runs/cfgcheck/<run>.yaml，由 fc_config_check.sh 预先生成）逐键断言（assert_cfg.py）：
#      parquet 的 sequence_id、回放、palm 容差（逐帧一臂不得有）、scene.support、buffer、步数、世界数、种子。任何一条不符就停整条链
#   2. 冒烟：逐条 fc_run（DONE 跳过；有残留 state_* 没有 DONE 记 SKIPPED，不续训）→ smoke_check → 256 世界 diag_rollout
#      → 用评测器顶点算不动基线（经 record 落成 day2/bar_<冒烟 run>）→ 帧数核对。任何一步不过，这条的正式训练记 SKIPPED，继续下一条
#   3. 正式：冒烟通过的 run 逐条 fc_run（DONE 跳过；残留 state 没 DONE 记 SKIPPED；失败记 FAILED，继续下一条）
# 期望表（TSV，第一行是表头）：run smoke sequence_id playback(frame|real) src_frames support(true|false) pos_tol ori_tol capacity seed xeval(yes|no)
#   期望帧数：逐帧 = src_frames；真实时长 = int(round((src_frames − 1) / 30 × 50)) + 1（同上游 resample_times）。pos_tol / ori_tol 两种回放的行都填，
#   逐帧一臂训练时不用（断言它没有容差键），评测链的交叉评测按它放宽。xeval 只给评测链用。
# 用法（仓库根）：stages/policy/day2_train_chain.sh <期望表> <冒烟队列> <正式队列> <冒烟显存上限 MiB> <日志名>
# 日志 runs/logs/<日志名>.log，最后一行 DAY2_TRAIN_DONE（完成 x、失败 y、跳过 z）或 DAY2_TRAIN_FAILED（链本身出错）。
set -uo pipefail
cd "$(dirname "$0")/../.."
EXPECT=${1:?期望表}; SQ=${2:?冒烟队列}; FQ=${3:?正式队列}; PEAK=${4:?冒烟显存上限}; NAME=${5:?日志名}
mkdir -p runs/logs results/day2
exec >> "runs/logs/$NAME.log" 2>&1
say() { echo "=== $(date '+%F %T %Z') $*"; }
die() { say "$*"; say DAY2_TRAIN_FAILED; exit 1; }
DAY1_BASE11=e2934912858820b8; DAY1_FREEZE=df0cf35711a68fb3   # 两台机器 Day 1 run_record.jsonl 里的镜像指纹
SRC0="$(cat .v2d-source-commit 2>/dev/null || echo unknown)"
say "start $NAME, source $SRC0, 期望表 $EXPECT"
MARK="runs/.chain-active-$NAME"   # scripts/dev/remote 见到 runs/.chain-active-* 就拒绝同步（同步会改写来历、换掉链后面才调用的脚本）
echo "$NAME $SRC0 $(date '+%F %T %Z')" > "$MARK"; trap 'rm -f "$MARK"' EXIT
case "$SRC0" in *-dirty*|*-syncing*|unknown) die "来历 $SRC0 不干净，先提交再同步" ;; esac
check_src() { [ "$(cat .v2d-source-commit 2>/dev/null || echo unknown)" = "$SRC0" ] || die "来历变了（开头 $SRC0，现在 $(cat .v2d-source-commit 2>/dev/null)），停下"; }
gpu_check() { local o; o="$(nvidia-smi --query-compute-apps=pid --format=csv,noheader | tr -d ' ')"; [ -z "$o" ] || die "GPU 上有别的进程（$o），停下"; }
qline() { grep -v '^[[:space:]]*#' "$1" | awk -v r="$2" '{for (i = 1; i <= NF; i++) if ($i == r) {print; exit}}'; }
run_q() {  # run_q <队列行>：带行首的环境变量调 fc_run.sh，返回它的退出码
  local tok envs=() i=0
  read -r -a tok <<< "$1"
  while (( i < ${#tok[@]} )) && [[ ${tok[$i]} =~ ^[A-Z_][A-Z0-9_]*= ]]; do envs+=("${tok[$i]}"); i=$((i + 1)); done
  env "${envs[@]}" bash stages/policy/fc_run.sh "${tok[@]:$i}" < /dev/null
}
exp_frames() { python3 -c 'import sys; n = int(sys.argv[2]); print(n if sys.argv[1] == "frame" else int(round((n - 1) / 30.0 * 50.0)) + 1)' "$1" "$2"; }
leftover() { [ ! -f "runs/flash_chord/$1/DONE" ] && compgen -G "runs/flash_chord/$1/state_*.safetensors" > /dev/null; }

mapfile -t ROWS < <(tail -n +2 "$EXPECT" | grep -v '^[[:space:]]*$')
[ "${#ROWS[@]}" -gt 0 ] || die "期望表 $EXPECT 没有数据行"
gpu_check

# 1. 正向核对
for row in "${ROWS[@]}"; do
  IFS=$'\t' read -r run smoke seq pb src support pos ori cap seed xev <<< "$row"; frames="$(exp_frames "$pb" "$src")"
  for r in "$smoke" "$run"; do
    [ -n "$(qline "$( [ "$r" = "$smoke" ] && echo "$SQ" || echo "$FQ")" "$r")" ] || die "队列里没有 $r"
    y=runs/cfgcheck/$r.yaml; [ -f "$y" ] || die "缺 $y：先在本机跑 fc_config_check.sh"
    read -r -a qt <<< "$(qline "$( [ "$r" = "$smoke" ] && echo "$SQ" || echo "$FQ")" "$r")"; j=0
    while [[ ${qt[$j]} =~ ^[A-Z_][A-Z0-9_]*= ]]; do j=$((j + 1)); done
    steps=${qt[$((j + 3))]}; [ "$r" = "$run" ] && [ "$steps" != 349999104 ] && die "$r 的正式步数是 $steps，不是 349999104"
    if [ "$pb" = real ]; then play=(task.source_frame_playback=false "embodiment.config.frame_position_tolerance=$pos" "embodiment.config.frame_orientation_tolerance=$ori")
    else play=(task.source_frame_playback=true '!embodiment.config.frame_position_tolerance' '!embodiment.config.frame_orientation_tolerance'); fi
    scripts/dev/in-flash-chord "python /repo/stages/policy/assert_cfg.py /repo/$y 'task.parquet~=sequence_id=$seq/robot_name=g1/data.parquet' ${play[*]} scene.support=$support training.replay.capacity=$cap training.total_environment_steps=$steps scene.world_count=2048 reset.seed=$seed training.seed=$seed task.motion_speed=1.0" \
      || die "$r 的展开配置与期望表不符"
  done
done
say "正向核对：${#ROWS[@]} 条 run 的冒烟与正式配置都与期望表一致"

# 2. 冒烟
declare -A OK
nd=0; nf=0; ns=0
for row in "${ROWS[@]}"; do
  IFS=$'\t' read -r run smoke seq pb src support pos ori cap seed xev <<< "$row"; frames="$(exp_frames "$pb" "$src")"
  check_src; gpu_check
  S=runs/flash_chord/$smoke
  if [ -f "$S/DONE" ]; then say "冒烟 $smoke 已 DONE"
  elif leftover "$smoke"; then say "冒烟 $smoke 有残留 state 没有 DONE：SKIPPED，$run 也跳过"; ns=$((ns + 1)); continue
  else
    say "冒烟 $smoke"
    run_q "$(qline "$SQ" "$smoke")" || { say "冒烟 $smoke 失败：$run SKIPPED"; ns=$((ns + 1)); continue; }
  fi
  read -r -a qt <<< "$(qline "$SQ" "$smoke")"; j=0; while [[ ${qt[$j]} =~ ^[A-Z_][A-Z0-9_]*= ]]; do j=$((j + 1)); done
  ssteps=${qt[$((j + 3))]}   # 冒烟步数取自队列行（B-rt 的冒烟加长到跨过第一个 curriculum 阶段与 checkpoint）
  stages/policy/smoke_check.sh "$smoke" "$ssteps" "$PEAK" "$DAY1_BASE11" "$DAY1_FREEZE" || { say "冒烟判据没过：$run SKIPPED"; ns=$((ns + 1)); continue; }
  mkdir -p "runs/diag/$smoke"
  V2D_GPU=1 V2D_CONTAINER_NAME="diag-$smoke" scripts/dev/in-flash-chord \
    "cd /workspace && python /repo/stages/evaluate/diag_rollout.py /repo/$S/policy_$ssteps.safetensors /repo/runs/diag/$smoke/rollout_w256 --worlds 256" \
    || { say "$smoke 的 256 世界 diag_rollout 失败：$run SKIPPED"; ns=$((ns + 1)); continue; }
  scripts/dev/record "day2/bar_$smoke" scripts/dev/in-flash-chord "python /repo/stages/evaluate/static_bar_from_rollout.py /repo/runs/diag/$smoke/rollout_w256.npz" \
    || { say "$smoke 的不动基线没算出来：$run SKIPPED"; ns=$((ns + 1)); continue; }
  got="$(sed -n 's/^ *summary_json //p' "results/day2/bar_$smoke.txt" | python3 -c 'import json, sys; print(json.loads(sys.stdin.read())["frames"])')"
  [ "$got" = "$frames" ] || { say "$smoke 的参考是 $got 帧，期望 $frames：$run SKIPPED"; ns=$((ns + 1)); continue; }
  say "冒烟 $smoke 通过：$got 帧，不动基线见 results/day2/bar_$smoke.txt"
  OK[$run]=1
done

# 3. 正式
for row in "${ROWS[@]}"; do
  IFS=$'\t' read -r run smoke seq pb src support pos ori cap seed xev <<< "$row"; frames="$(exp_frames "$pb" "$src")"
  [ -n "${OK[$run]:-}" ] || continue
  check_src; gpu_check
  if [ -f "runs/flash_chord/$run/DONE" ]; then say "$run 已 DONE"; nd=$((nd + 1)); continue; fi
  if leftover "$run"; then say "$run 有残留 state 没有 DONE：SKIPPED（续训不恢复 replay，要从 0 重来就先移走该目录）"; ns=$((ns + 1)); continue; fi
  say "正式 $run"
  run_q "$(qline "$FQ" "$run")"; rc=$?
  if [ "$rc" = 0 ] && [ -f "runs/flash_chord/$run/DONE" ]; then
    segs="$(grep -c '"event": "start"' "runs/flash_chord/$run/run_record.jsonl")"
    say "$run 完成（$segs 段）"; nd=$((nd + 1))
  elif [ "$rc" = 4 ]; then
    say "$run 显存不足（fc_run 退出码 4）：剩下的 run 同样的配置也放不下，全部跳过"; nf=$((nf + 1)); break
  else
    say "$run 失败（退出码 $rc），继续下一条"; nf=$((nf + 1))
  fi
done
say "DAY2_TRAIN_DONE（完成 $nd、失败 $nf、跳过 $ns）"
