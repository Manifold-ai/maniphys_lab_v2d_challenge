#!/usr/bin/env bash
# v0.4.0 训出的 checkpoint 能否在 8c778f9 评测器里加载、导出（训练机上、仓库根执行，放 tmux）。计划 agent-doc/plan-box6-and-eval-runtime-2026-10-01.md 第 3.3 节。
# 用法：V2D_FC_SRC=<8c778f9 副本> [V2D_WAIT_FOR_EVAL_LOG=<上一段评测链日志>] stages/evaluate/compat_8c778f9.sh <清单> <日志名>
# 清单（stages/evaluate/compat/<机器>.tsv）每行 tab 分隔：<类型> <run> <步数> <世界数>；# 开头为注释。四种类型：
#   export  fc_export.sh 按 kit 的做法导出（metrics JSON + 轨迹 parquet），再用 check_export.py 核结构与来历（判据 P1–P3）
#   eval    fc_export.sh 只写 metrics JSON（V2D_EXPORT_TRAJ=0），与同一 checkpoint 在 v0.4.0 评测器下的 eval_<步数>_w<世界数>.json
#           用 eval_compare.py 比：同一 sha256、ΔADD-AUC < 0.005、chord_sr |z| < 3（判据 P4，与 Day 2 恒等覆盖核对同一道闸）
#   guard、negctl  含 NaN 的 policy 的两道对照，判定见 compat_expect.sh
# 每行经 scripts/dev/record 落盘到 results/submission/compat/<清单名>_<类型>_<run>_w<世界数>*.txt（不过的是 .txt.failed）。
# 0. 设了 V2D_WAIT_FOR_EVAL_LOG：每分钟看它的最后一行，变成 DAY2_EVAL_DONE / DAY2_EVAL_FAILED 才开始。从启动起就写长链标记
#    runs/.chain-active-<日志名>，等待期间也挡住同步。
# 1. GPU 上有进程、没设 V2D_FC_SRC、或它核不过（fc_src_check.py + flash_chord-8c778f9.sha256）：COMPAT_FAIL，停。
# 2. 逐行执行；某行不过不停，接着做下一行。
# 3. 门槛文件 runs/logs/<日志名>.gate 写一行 “DAY2_TRAIN_DONE（完成 <export 通过数>、失败 <export 不过数>、…）”：方盒训练链的
#    chain_after.sh 把它当“上一段训练日志”，门槛设成清单里 export 的行数，export 全过才开训练（计划第 4.4 节）。eval、guard、negctl
#    不进门槛：它们管的是已有结果能不能沿用、守卫灵不灵，与方盒怎么训无关。
# 4. 日志倒数第二行 COMPAT_PASS / COMPAT_FAIL，最后一行 DAY2_EVAL_DONE（成功 x、失败 y）：沿用评测链的结束行，chain_after.sh 靠它判断这一段结束。
set -uo pipefail
cd "$(dirname "$0")/../.."
LIST=${1:?用法见文件头}; NAME=${2:?用法见文件头}
TAG="$(basename "$LIST" .tsv)"
LOG="runs/logs/$NAME.log"; GATE="runs/logs/$NAME.gate"; MARK="runs/.chain-active-$NAME"
mkdir -p runs/logs
touch "$MARK"; trap 'rm -f "$MARK"' EXIT
say() { echo "=== $(date '+%F %T %Z') $*" | tee -a "$LOG"; }
ok=0; bad=0; xok=0; xbad=0
gate() { echo "=== $(date '+%F %T %Z') DAY2_TRAIN_DONE（完成 ${xok}、失败 ${xbad}、跳过 0、发散 0）" > "$GATE"; }
stop() { say "$*"; gate; say "COMPAT_FAIL（没做完）"; say "DAY2_EVAL_FAILED"; exit 1; }
rm -f "$GATE"
say "start ${NAME}：清单 ${LIST}，V2D_FC_SRC=${V2D_FC_SRC:-未设}，来历 $(cat .v2d-source-commit 2>/dev/null || echo unknown)"
if [ -n "${V2D_WAIT_FOR_EVAL_LOG:-}" ]; then
  say "等 $V2D_WAIT_FOR_EVAL_LOG 的最后一行变成 DAY2_EVAL_DONE / DAY2_EVAL_FAILED"
  until grep -qE "DAY2_EVAL_(DONE|FAILED)" < <(tail -1 "$V2D_WAIT_FOR_EVAL_LOG" 2>/dev/null); do sleep "${V2D_POLL_S:-60}"; done
  say "上一段评测链已结束：$(tail -1 "$V2D_WAIT_FOR_EVAL_LOG")"
fi
others="$(nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null | tr -d ' ')"
[ -z "$others" ] || stop "GPU 上有别的进程（${others}），停下"
[ -n "${V2D_FC_SRC:-}" ] || stop "没设 V2D_FC_SRC（要 make_fc_src_8c778f9.sh 生成的副本），停下"
scripts/dev/record "submission/compat/${TAG}_fc_src" python3 stages/policy/fc_src_check.py "$V2D_FC_SRC" third_party/patches/flash_chord-8c778f9.sha256 >> "$LOG" 2>&1 \
  || stop "V2D_FC_SRC=${V2D_FC_SRC} 不是核对过的 8c778f9 副本（results/submission/compat/${TAG}_fc_src.txt.failed），停下"

exec 3< "$LIST"
while IFS=$'\t' read -r -u 3 kind run step w _; do
  case "$kind" in ''|'#'*) continue ;; esac
  key="submission/compat/${TAG}_${kind}_${run}_w${w}"
  case "$kind" in
    export)
      if V2D_EXPORT_WORLDS="$w" scripts/dev/record "$key" stages/evaluate/fc_export.sh "$run" "$step" >> "$LOG" 2>&1 < /dev/null \
         && scripts/dev/record "${key}_check" python3 stages/evaluate/check_export.py "$run" "$step" "$w" >> "$LOG" 2>&1 < /dev/null; then
        ok=$((ok + 1)); xok=$((xok + 1)); say "export ${run}（${w} 世界）：导出、核对都通过"
      else
        bad=$((bad + 1)); xbad=$((xbad + 1)); say "export ${run}（${w} 世界）：不过，见 results/${key}*"
      fi ;;
    eval)
      d="runs/flash_chord/$run/export_8c778f9/s${step}_w${w}"
      if V2D_EXPORT_WORLDS="$w" V2D_EXPORT_TRAJ=0 scripts/dev/record "$key" stages/evaluate/fc_export.sh "$run" "$step" >> "$LOG" 2>&1 < /dev/null \
         && j="$(ls "$d"/episode_*.json 2>/dev/null | head -1)" && [ -n "$j" ] \
         && scripts/dev/record "${key}_compare" python3 stages/policy/eval_compare.py "$j" "runs/flash_chord/$run/eval_${step}_w${w}.json" \
              --max-add-auc-diff 0.005 --max-chord-z 3 >> "$LOG" 2>&1 < /dev/null; then
        ok=$((ok + 1)); say "eval ${run}（${w} 世界）：与 v0.4.0 评测器的结果一致（CONSISTENT）"
      else
        bad=$((bad + 1)); say "eval ${run}（${w} 世界）：不一致或没评完，见 results/${key}*"
      fi ;;
    guard|negctl)
      if V2D_RECORD_TRACEBACK_OK=1 scripts/dev/record "$key" stages/evaluate/compat_expect.sh "$kind" "$run" "$step" "$w" >> "$LOG" 2>&1 < /dev/null; then
        ok=$((ok + 1)); say "$kind ${run}：符合期望（$(grep -h 'COMPAT_EXPECT_OK' "results/$key.txt" | tail -1)）"
      else
        bad=$((bad + 1)); say "$kind ${run}：不符合期望，见 results/${key}.txt.failed"
      fi ;;
    *) bad=$((bad + 1)); say "清单里有未知类型 ${kind}（${run}），跳过" ;;
  esac
done
exec 3<&-
gate
if [ "$bad" = 0 ]; then say "COMPAT_PASS（${ok} 行全部符合）"; else say "COMPAT_FAIL（${bad} 行不符合，共 $((ok + bad)) 行；export 通过 ${xok}、不过 ${xbad}）"; fi
say "DAY2_EVAL_DONE（成功 ${ok}、失败 ${bad}）"
