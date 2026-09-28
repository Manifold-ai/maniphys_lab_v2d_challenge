#!/usr/bin/env bash
# Day 1b（在 ml40 上执行，放 tmux，不依赖 Mac 在线）。计划见 agent-doc/plan-day1b-2026-09-27.md（第 2 版）。
#   1. 镜像指纹缓存挪开，让冒烟重新计算 base11 与依赖 freeze
#   2. 冒烟（queues/ml40_day1b_smoke.txt，W&B 记到 v2d-selftest）→ 冒烟判据全过才继续
#   3. 正式满配 snack_box（queues/ml40_day1b.txt，V2D_MAX_RETRY=0：失败即停，不自动续训）
#   4. 4096 世界评测与输入清单（经 scripts/dev/record）
# 用法（仓库根）：tmux new-session -d -s v2d-day1b stages/policy/queues/ml40_day1b.sh
# 日志 runs/logs/ml40_day1b.log，最后一行 DAY1B_DONE 或 DAY1B_FAILED。
set -euo pipefail
cd "$(dirname "$0")/../../.."
mkdir -p runs/logs
exec >> runs/logs/ml40_day1b.log 2>&1
trap 'echo "=== $(date "+%F %T %Z") DAY1B_FAILED (line $LINENO)"' ERR
SMOKE=smoke-snackbox-w2048-cap10m-ml40; RUN=ctrl-snackbox-w2048-cap10m-ml40
DAY1_BASE11=e2934912858820b8; DAY1_FREEZE=df0cf35711a68fb3   # Day 1 满配 ep20 的 run_record.jsonl
say() { echo "=== $(date '+%F %T %Z') $*"; }
fail() { say "$*"; false; }
say "start, source $(cat .v2d-source-commit 2>/dev/null || echo unknown)"

# 1. 指纹缓存挪开（留作对照）
IMG="$(docker image inspect -f '{{.Id}}' flash_chord:latest)"
C="runs/cache/image-${IMG#sha256:}.json"
if [ -f "$C" ]; then mv "$C" "$C.day1"; say "指纹缓存挪到 $C.day1，冒烟时重新计算"; fi

# 2. 冒烟与判据
S=runs/flash_chord/$SMOKE; L=runs/logs/$SMOKE.s1.log
[ -f "$S/DONE" ] || stages/policy/fc_queue.sh stages/policy/queues/ml40_day1b_smoke.txt
[ -f "$S/DONE" ] || fail "冒烟没有 DONE"
grep -q "compiled FlashSAC JAX executables" "$L" || fail "冒烟日志没有 compiled FlashSAC JAX executables"
! grep -qE "RESOURCE_EXHAUSTED|exceeds the base limit" "$L" || fail "冒烟日志有显存错误"
[ "$(python3 stages/policy/ckpt_latest.py "$S")" = 4096000 ] || fail "冒烟最终 checkpoint 不是完整的 4096000"
grep -qE "wandb: Synced .*artifact" "$L" || fail "冒烟的 W&B 没有同步成功"
rec="$(grep '"event": "start"' "$S/run_record.jsonl" | tail -1)"
b11="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["image_base11_sha"])' "$rec")"
frz="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["deps_freeze_sha"])' "$rec")"
[ "$b11" = "$DAY1_BASE11" ] && [ "$frz" = "$DAY1_FREEZE" ] || fail "重算的镜像指纹 $b11 / $frz 与 Day 1 的 $DAY1_BASE11 / $DAY1_FREEZE 不同"
say "冒烟判据全过；重算的镜像指纹与 Day 1 相同（$b11 / $frz）"

# 3. 正式训练
stages/policy/fc_queue.sh stages/policy/queues/ml40_day1b.txt
[ -f "runs/flash_chord/$RUN/DONE" ] || fail "正式训练没有 DONE"
segs="$(grep -c '"event": "start"' "runs/flash_chord/$RUN/run_record.jsonl")"
[ "$segs" = 1 ] && say "正式训练一段跑完" || say "注意：正式训练有 $segs 段，按登记标为偏离（续训不恢复 replay）"

# 4. 评测与输入清单
scripts/dev/record "day1/eval_$RUN" stages/policy/fc_eval.sh "$RUN" 349999104
scripts/dev/record "day1/policy_inputs_${RUN}_on_ml40" python3 stages/policy/policy_inputs.py "runs/flash_chord/$RUN/policy_349999104.safetensors"
say DAY1B_DONE
