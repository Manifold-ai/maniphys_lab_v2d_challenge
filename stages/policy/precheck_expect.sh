#!/usr/bin/env bash
# 开链前预跑训练链的“正向核对”（与 stages/policy/day2_train_chain.sh 第 1 步相同的断言），不开训练、不占 GPU。训练机上、仓库根执行。
# 用途：一段队列要等别的链跑完才自动开跑（例如批量的 B 段），它开头的核对要是不过，整条链就停、GPU 空着没人管；开跑前先在这里核一遍。
# 每条 run（冒烟与正式）：队列里有这一行、runs/cfgcheck/<run>.yaml 存在（fc_config_check.sh 生成）、正式步数 349999104，
# 再在容器里用 assert_cfg.py 断言 parquet 的 sequence_id、回放（逐帧一臂不得有容差键）、scene.support、buffer、步数、世界数、种子、motion_speed。
# 用法：stages/policy/precheck_expect.sh <期望表> <冒烟队列> <正式队列>；全过退出码 0，最后一行 PRECHECK_OK（n 条 run）。
set -uo pipefail
cd "$(dirname "$0")/../.."
EXPECT=${1:?期望表}; SQ=${2:?冒烟队列}; FQ=${3:?正式队列}
bad=0
qline() { grep -v '^[[:space:]]*#' "$1" | awk -v r="$2" '{for (i = 1; i <= NF; i++) if ($i == r) {print; exit}}'; }
mapfile -t ROWS < <(tail -n +2 "$EXPECT" | grep -v '^[[:space:]]*$')
[ "${#ROWS[@]}" -gt 0 ] || { echo "期望表 $EXPECT 没有数据行"; exit 1; }
for row in "${ROWS[@]}"; do
  IFS=$'\t' read -r run smoke seq pb src support pos ori cap seed xev <<< "$row"
  for r in "$smoke" "$run"; do
    q="$( [ "$r" = "$smoke" ] && echo "$SQ" || echo "$FQ")"
    line="$(qline "$q" "$r")"
    [ -n "$line" ] || { echo "FAIL $r：队列 $q 里没有这一行"; bad=$((bad + 1)); continue; }
    y=runs/cfgcheck/$r.yaml
    [ -f "$y" ] || { echo "FAIL $r：缺 $y（先跑 fc_config_check.sh）"; bad=$((bad + 1)); continue; }
    read -r -a qt <<< "$line"; j=0
    while [[ ${qt[$j]} =~ ^[A-Z_][A-Z0-9_]*= ]]; do j=$((j + 1)); done
    steps=${qt[$((j + 3))]}
    if [ "$r" = "$run" ] && [ "$steps" != 349999104 ]; then echo "FAIL $r：正式步数 $steps"; bad=$((bad + 1)); continue; fi
    if [ "$pb" = real ]; then play=(task.source_frame_playback=false "embodiment.config.frame_position_tolerance=$pos" "embodiment.config.frame_orientation_tolerance=$ori")
    else play=(task.source_frame_playback=true '!embodiment.config.frame_position_tolerance' '!embodiment.config.frame_orientation_tolerance'); fi
    out="$(scripts/dev/in-flash-chord "python /repo/stages/policy/assert_cfg.py /repo/$y 'task.parquet~=sequence_id=$seq/robot_name=g1/data.parquet' ${play[*]} scene.support=$support training.replay.capacity=$cap training.total_environment_steps=$steps scene.world_count=2048 reset.seed=$seed training.seed=$seed task.motion_speed=1.0" 2>&1)"; rc=$?
    echo "$out" | tail -1
    [ "$rc" = 0 ] || { echo "FAIL $r：断言不过"; bad=$((bad + 1)); }
  done
done
if [ "$bad" = 0 ]; then echo "PRECHECK_OK（${#ROWS[@]} 条 run）"; else echo "PRECHECK_FAIL（$bad 处不过）"; exit 1; fi
