#!/usr/bin/env bash
# 提交用的批量导出（训练机上、仓库根执行，放 tmux）：按导出清单把每条 episode 的 policy 用 8c778f9 评测器导成 1 个世界的轨迹。不上传。
# 计划 agent-doc/plan-submission-exports-2026-10-02.md 第 3.2 节。
# 用法：V2D_FC_SRC=<8c778f9 副本> [V2D_WAIT_FOR_EVAL_LOG=<上一段评测链日志>] [V2D_REQUIRE_GATE=<compat 门槛文件>] \
#         stages/evaluate/export_chain.sh <导出清单> <日志名>
#       预检：V2D_EXPORT_CHAIN_DRYRUN=1 加上同样的环境与参数（见文末“预检”）
# 清单（stages/evaluate/exports/<机器>.tsv，export_map.py 生成）每行 tab 分隔：档位 episode run 步数；# 开头为注释。
# 0. 日志 runs/logs/<日志名>.log 或结果表 runs/exports/<日志名>.tsv 已存在、清单读不了或没有行：拒绝（退出码 2，不写日志）。
# 1. 设了 V2D_WAIT_FOR_EVAL_LOG：每分钟看它的最后一行，变成 DAY2_EVAL_DONE / DAY2_EVAL_FAILED 才开始。从启动起就写长链标记
#    runs/.chain-active-<日志名>。本日志里不出现这两个结束标记的原文（同 compat_8c778f9.sh 的教训）。
# 2. 设了 V2D_REQUIRE_GATE：门槛文件必须是“完成 1”（compat 的导出全部成功），否则停。GPU 上有进程、没设 V2D_FC_SRC 或它核不过，也停。
# 3. 逐行（某行不过不停，接着做下一行）：
#    run 没有 DONE → no_done；有 NONFINITE（规矩一：含 NaN 的 policy 不导出；不回退，记缺，等用户定）→ nonfinite。
#    否则 fc_export.sh 导出（1 个世界、写轨迹），退出码 0 再跑 check_export.sh 核结构与来历：
#      都过 → ok；
#      fc_export 退出码 13（评测器报 must disable task failure termination）→ 规矩二：按步数从大到小试同一 run 里更早的 policy，
#        最多 V2D_FALLBACK_MAX 份（默认 8）：fc_export 退出码 12（非有限、读不了）跳过，13 继续往前，导出与核对都过的那一步就用；
#        别的失败停在这一条（fallback_failed）。用上的那一步再在 8c778f9 下补评 4096 世界（只写 JSON）：
#        补评成功 → fallback；补评失败 → fallback_noeval（轨迹能交，但按计划第 5 节不进候选，人来看）；
#      fc_export 其他退出码 → export_failed；check_export 不过 → check_failed。
#    每行写进结果表 runs/exports/<日志名>.tsv：档位 episode run 用的步数 状态 JSON parquet JSON 的 sha256 parquet 的 sha256。
#    每次导出、核对经 scripts/dev/record 落盘到 results/submission/exports/<日志名>_<run>_s<步数>[_check|_w4096].txt。
# 4. 日志最后一行 EXPORT_CHAIN_DONE（成功 x、失败 y），停在开头的检查时是 EXPORT_CHAIN_FAILED。成功 = ok + fallback + fallback_noeval。
set -uo pipefail
cd "$(dirname "$0")/../.."
LIST=${1:?用法见文件头}; NAME=${2:?用法见文件头}
LOG="runs/logs/$NAME.log"; OUT="runs/exports/$NAME.tsv"; MARK="runs/.chain-active-$NAME"
DRY="${V2D_EXPORT_CHAIN_DRYRUN:-0}"; FMAX="${V2D_FALLBACK_MAX:-8}"
[ -e "$LOG" ] || [ -e "$OUT" ] && { echo "export_chain: $LOG 或 $OUT 已存在，拒绝（确认后改名或删掉再起）" >&2; exit 2; }
[ -r "$LIST" ] || { echo "export_chain: 读不了清单 $LIST" >&2; exit 2; }
NROW="$(grep -cvE '^(#|$)' "$LIST")"
[ "$NROW" -gt 0 ] || { echo "export_chain: 清单 $LIST 没有行" >&2; exit 2; }
[[ $FMAX =~ ^[0-9]+$ ]] || { echo "export_chain: V2D_FALLBACK_MAX 必须是非负整数" >&2; exit 2; }

if [ "$DRY" = 1 ]; then
  bad=0; pend=0
  chk() { if eval "$2" >/dev/null 2>&1; then echo "  ok   $1"; else echo "  FAIL $1"; bad=$((bad + 1)); fi; }
  echo "== 预检 ${NAME}：清单 ${LIST}（${NROW} 行），V2D_FC_SRC=${V2D_FC_SRC:-未设}，来历 $(cat .v2d-source-commit 2>/dev/null || echo unknown)"
  echo "  ok   $LOG 与 $OUT 都不存在"
  chk "check_export 能跑：$(stages/evaluate/check_export.sh --probe 2>&1)" "stages/evaluate/check_export.sh --probe"
  if [ -n "${V2D_WAIT_FOR_EVAL_LOG:-}" ]; then chk "要等的评测链日志 $V2D_WAIT_FOR_EVAL_LOG 已存在" "[ -f '$V2D_WAIT_FOR_EVAL_LOG' ]"; fi
  [ -n "${V2D_REQUIRE_GATE:-}" ] && echo "  --   门槛 ${V2D_REQUIRE_GATE}：$(cat "$V2D_REQUIRE_GATE" 2>/dev/null || echo 还没写，开跑时再看)"
  chk "V2D_FC_SRC 是核对过的 8c778f9 副本" "[ -n '${V2D_FC_SRC:-}' ] && python3 stages/policy/fc_src_check.py '${V2D_FC_SRC:-/nonexistent}' third_party/patches/flash_chord-8c778f9.sha256"
  exec 3< "$LIST"
  while IFS=$'\t' read -r -u 3 tier ep run step _; do
    case "$tier" in ''|'#'*) continue ;; esac
    d="runs/flash_chord/$run"
    if [ ! -f "$d/DONE" ]; then echo "  --   Tier $tier ep${ep} ${run}：还没有 DONE（还在训或排队），开跑时再看"; pend=$((pend + 1)); continue; fi
    if [ -f "$d/NONFINITE" ]; then echo "  --   Tier $tier ep${ep} ${run}：有 NONFINITE，开跑时按规矩一记缺"; pend=$((pend + 1)); continue; fi
    out="$(V2D_EXPORT_DRYRUN=1 V2D_EXPORT_WORLDS=1 stages/evaluate/fc_export.sh "$run" "$step" 2>&1 < /dev/null)"; rc=$?
    if [ "$rc" = 0 ]; then echo "  ok   Tier $tier ep${ep} ${run}：fc_export 预检退出码 0（$(head -1 <<< "$out" | sed 's/^fc_export: DRYRUN //')）"
    else echo "  FAIL Tier $tier ep${ep} ${run}：fc_export 预检退出码 ${rc}：$(tail -1 <<< "$out")"; bad=$((bad + 1)); fi
  done
  exec 3<&-
  echo "  --   还没训完或有 NONFINITE 的 ${pend} 行，开跑时按 no_done / nonfinite 记"
  if [ "$bad" = 0 ]; then echo "EXPORT_DRYRUN_OK"; exit 0; else echo "EXPORT_DRYRUN_FAIL $bad"; exit 1; fi
fi

mkdir -p runs/logs runs/exports
touch "$MARK"; trap 'rm -f "$MARK"' EXIT
say() { echo "=== $(date '+%F %T %Z') $*" | tee -a "$LOG"; }
stop() { say "$*"; say "EXPORT_CHAIN_FAILED"; exit 1; }
printf 'tier\tepisode\trun\tstep\tstatus\tjson\tparquet\tjson_sha256\tparquet_sha256\n' > "$OUT"
say "start ${NAME}：清单 ${LIST}（${NROW} 行），V2D_FC_SRC=${V2D_FC_SRC:-未设}，回退最多 ${FMAX} 份，来历 $(cat .v2d-source-commit 2>/dev/null || echo unknown)"
if [ -n "${V2D_WAIT_FOR_EVAL_LOG:-}" ]; then
  say "等 $V2D_WAIT_FOR_EVAL_LOG 结束（它的最后一行变成评测链的结束行）"
  until grep -qE "DAY2_EVAL_(DONE|FAILED)" < <(tail -1 "$V2D_WAIT_FOR_EVAL_LOG" 2>/dev/null); do sleep "${V2D_POLL_S:-60}"; done
  say "上一段评测链已结束：$(tail -1 "$V2D_WAIT_FOR_EVAL_LOG" | sed -E 's/DAY2_EVAL_DONE/评测链完成/; s/DAY2_EVAL_FAILED/评测链失败/')"
fi
if [ -n "${V2D_REQUIRE_GATE:-}" ]; then
  grep -q '完成 1、' "$V2D_REQUIRE_GATE" 2>/dev/null \
    || stop "门槛 $V2D_REQUIRE_GATE 不是“完成 1”（compat 的导出没有全部成功），不导出：$(cat "$V2D_REQUIRE_GATE" 2>/dev/null || echo 没有门槛文件)"
fi
others="$(nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null | tr -d ' ')"
[ -z "$others" ] || stop "GPU 上有别的进程（${others//$'\n'/,}），停下"
[ -n "${V2D_FC_SRC:-}" ] || stop "没设 V2D_FC_SRC，停下"
scripts/dev/record "submission/exports/${NAME}_fc_src" python3 stages/policy/fc_src_check.py "$V2D_FC_SRC" third_party/patches/flash_chord-8c778f9.sha256 >> "$LOG" 2>&1 \
  || stop "V2D_FC_SRC=${V2D_FC_SRC} 不是核对过的 8c778f9 副本（results/submission/exports/${NAME}_fc_src.txt.failed），停下"

ok=0; bad=0
shaof() { [ -f "$1" ] && sha256sum "$1" | cut -d' ' -f1; }
row() {  # row <档位> <ep> <run> <步数> <状态>：步数是这一行最后用的（或试过的）那一步
  local j="" q=""
  j="$(ls "runs/flash_chord/$3/export_8c778f9/s${4}_w1"/episode_*.json 2>/dev/null | head -1)"
  [ -n "$j" ] && [ -f "${j%.json}.parquet" ] && q="${j%.json}.parquet"
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" "$5" "$j" "$q" "$(shaof "$j")" "$(shaof "$q")" >> "$OUT"
  case "$5" in ok|fallback|fallback_noeval) ok=$((ok + 1)) ;; *) bad=$((bad + 1)) ;; esac
}
export_one() {  # export_one <run> <步数>：0 导出与核对都过；12、13 是 fc_export 的退出码；3 导出其他失败；4 核对不过
  local rc=0
  V2D_EXPORT_WORLDS=1 V2D_EXPORT_TRAJ=1 scripts/dev/record "submission/exports/${NAME}_${1}_s${2}" \
    stages/evaluate/fc_export.sh "$1" "$2" >> "$LOG" 2>&1 < /dev/null || rc=$?
  case "$rc" in 0) ;; 12|13) return "$rc" ;; *) return 3 ;; esac
  scripts/dev/record "submission/exports/${NAME}_${1}_s${2}_check" stages/evaluate/check_export.sh "$1" "$2" 1 >> "$LOG" 2>&1 < /dev/null || return 4
  return 0
}
exec 3< "$LIST"
while IFS=$'\t' read -r -u 3 tier ep run step _; do
  case "$tier" in ''|'#'*) continue ;; esac
  d="runs/flash_chord/$run"
  if [ ! -f "$d/DONE" ]; then row "$tier" "$ep" "$run" "$step" no_done; say "Tier $tier ep${ep} ${run}：没有 DONE，不导出"; continue; fi
  if [ -f "$d/NONFINITE" ]; then row "$tier" "$ep" "$run" "$step" nonfinite; say "Tier $tier ep${ep} ${run}：有 NONFINITE（规矩一），不导出，这条记缺"; continue; fi
  export_one "$run" "$step"; rc=$?
  case "$rc" in
    0) row "$tier" "$ep" "$run" "$step" ok; say "Tier $tier ep${ep} ${run}：第 ${step} 步导出、核对都通过"; continue ;;
    4) row "$tier" "$ep" "$run" "$step" check_failed; say "Tier $tier ep${ep} ${run}：第 ${step} 步导出了，但 check_export 不过"; continue ;;
    13) ;;
    *) row "$tier" "$ep" "$run" "$step" export_failed; say "Tier $tier ep${ep} ${run}：第 ${step} 步导出失败（退出码 ${rc}）"; continue ;;
  esac
  say "Tier $tier ep${ep} ${run}：第 ${step} 步报 must disable task failure termination，按规矩二往前退（最多 ${FMAX} 份）"
  used=""; tried=0; last="$step"
  for s in $(ls "$d"/policy_*.safetensors 2>/dev/null | sed -E 's/.*policy_([0-9]+)\.safetensors$/\1/' | sort -rn); do
    [ "$s" -lt "$step" ] || continue
    [ "$tried" -lt "$FMAX" ] || { say "  已试 ${FMAX} 份，不再往前"; break; }
    tried=$((tried + 1)); last="$s"
    export_one "$run" "$s"; r2=$?
    case "$r2" in
      0) used="$s"; break ;;
      12) say "  第 ${s} 步的 policy 非有限或读不了，跳过" ;;
      13) say "  第 ${s} 步同样报终止错误，继续往前" ;;
      *) say "  第 ${s} 步导出或核对失败（${r2}），停在这一条"; break ;;
    esac
  done
  if [ -z "$used" ]; then row "$tier" "$ep" "$run" "$last" fallback_failed; say "Tier $tier ep${ep} ${run}：回退没有找到能用的 checkpoint"; continue; fi
  if V2D_EXPORT_WORLDS=4096 V2D_EXPORT_TRAJ=0 scripts/dev/record "submission/exports/${NAME}_${run}_s${used}_w4096" \
       stages/evaluate/fc_export.sh "$run" "$used" >> "$LOG" 2>&1 < /dev/null; then
    row "$tier" "$ep" "$run" "$used" fallback; say "Tier $tier ep${ep} ${run}：按规矩二改用第 ${used} 步，4096 世界补评完成"
  else
    row "$tier" "$ep" "$run" "$used" fallback_noeval; say "Tier $tier ep${ep} ${run}：按规矩二改用第 ${used} 步，但 4096 世界补评失败（不进候选，人来看）"
  fi
done
exec 3<&-
say "EXPORT_CHAIN_DONE（成功 ${ok}、失败 ${bad}）"
