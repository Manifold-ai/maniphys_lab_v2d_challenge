#!/usr/bin/env bash
# k-fix 方案 4 第 6 步：用现有 checkpoint 对新参考评测与导出（mf4090 上、仓库根执行，放 tmux 经 scripts/dev/record 落盘）。
# 计划 agent-doc/plan-t3-kfix-2026-10-16.md “方案 4 的执行细则”第 6、7 步。清单（默认 stages/evaluate/exports/kfix_t3_mf4090.tsv）每行：
#   run、步数、参考 parquet（容器内 /repo/... 路径；plain 行写 -）、后缀、模式。
#   plain：不换参考的普通路径（fc_export.sh 不设 V2D_EXPORT_PARQUET），评 4096 世界，用作同一评测器（fc_8c778f9）下的旧值；
#   idchk：这条 run 原来训练用的 parquet 经 eval_playback_override.py 的包装层评 4096 世界，与 plain 比，看包装层改不改结果；
#   kfix：先评 4096 世界（只写指标），再导出 1 个世界（带轨迹，给打包用）。
# 为什么要 plain：10/11 的旧评测挂的是 third_party 的 v0.4.0，现在走 fc_8c778f9（改了 11 个文件），旧值要用同一评测器重评才能比。
# idchk 行评完就调 kfix_reexport_table.py --check：包装层不恒等就停（最后一行 KFIX_REEXPORT_STOPPED idchk，后面不占 GPU）；
# 评测器不一致（plain 与 10/11 的差超过容差）时，之后每条 kfix 行先补一条它自己的 plain，判据 5 的旧值都用同一评测器的。
# 每一步都经 stages/evaluate/fc_export.sh：它核 checkpoint、NaN 守卫、GPU 占用，换参考时还核评测 JSON 里记的 parquet。一行失败不停，记下退出码；
# 最后跑 kfix_reexport_table.py 汇总并写结果表 runs/exports/kfix_t3_mf4090.tsv（判“换”、导出齐全的集，格式同 export_chain.sh）。
# 最后一行 KFIX_REEXPORT_DONE <失败步数>。
# 用法：V2D_FC_SRC=<8c778f9 副本> stages/evaluate/kfix_reexport.sh [清单]
set -uo pipefail
cd "$(dirname "$0")/../.."
L=${1:-stages/evaluate/exports/kfix_t3_mf4090.tsv}
[ -n "${V2D_FC_SRC:-}" ] || { echo "kfix_reexport: 要设 V2D_FC_SRC" >&2; exit 2; }
[ -f "$L" ] || { echo "kfix_reexport: 没有清单 ${L}" >&2; exit 2; }
echo "== $(hostname) $(date '+%F %T %Z') 来历 $(cat .v2d-source-commit 2>/dev/null)；清单 ${L}（md5 $(md5sum < "$L" | cut -c1-32)）"
fail=0; drift=0
plain_eval() {   # plain_eval <run> <步数>：不换参考、同一评测器的 4096 世界评测，后缀 _plain
  V2D_EXPORT_SUFFIX=_plain V2D_EXPORT_WORLDS=4096 V2D_EXPORT_TRAJ=0 stages/evaluate/fc_export.sh "$1" "$2" < /dev/null; local rc=$?
  echo "plain 4096 世界评测 退出码 ${rc}"; [ "$rc" = 0 ] || fail=$((fail + 1))
}
while IFS=$'\t' read -r run step pq suf mode <&3; do
  [ "$run" = run ] && continue
  echo "=== $(date '+%F %T %Z') ${run} ${step} ${mode} ${suf}"
  if [ "$mode" = plain ]; then plain_eval "$run" "$step"; continue; fi
  if [ "$mode" = kfix ] && [ "$drift" = 1 ]; then
    ep=$(printf %06d "$((10#$(echo "$run" | sed -E 's/^t3-ep([0-9]+)-.*/\1/')))")
    [ -f "runs/flash_chord/$run/export_8c778f9/s${step}_w4096_plain/episode_$ep.json" ] || plain_eval "$run" "$step"
  fi
  V2D_EXPORT_PARQUET=$pq V2D_EXPORT_SUFFIX=$suf V2D_EXPORT_WORLDS=4096 V2D_EXPORT_TRAJ=0 stages/evaluate/fc_export.sh "$run" "$step" < /dev/null; rc=$?
  echo "4096 世界评测 退出码 ${rc}"; [ "$rc" = 0 ] || fail=$((fail + 1))
  if [ "$mode" = idchk ]; then
    chk=$(python3 stages/evaluate/kfix_reexport_table.py "$L" --check 2>&1)
    printf '%s\n' "$chk" | grep -a -E "恒等核对|评测器核对|缺" || true
    last=$(printf '%s\n' "$chk" | tail -1)
    case "$last" in
      "KFIX_CHECK 恒等 一致") ;;
      "KFIX_CHECK 恒等 不一致") drift=1; echo "评测器不一致：之后每条 kfix 行先补 plain" ;;
      "KFIX_CHECK 恒等 缺") echo "没有 10/11 的旧评测可比，判据 5 用能找到的旧值" ;;
      *) echo "恒等核对没过（${last}），停（后面各行不跑）"; echo "KFIX_REEXPORT_STOPPED idchk"; exit 1 ;;
    esac
  fi
  if [ "$mode" = kfix ] && [ "$rc" = 0 ]; then
    V2D_EXPORT_PARQUET=$pq V2D_EXPORT_SUFFIX=$suf stages/evaluate/fc_export.sh "$run" "$step" < /dev/null; rc=$?
    echo "1 世界导出 退出码 ${rc}"; [ "$rc" = 0 ] || fail=$((fail + 1))
  fi
done 3< "$L"
python3 stages/evaluate/kfix_reexport_table.py "$L" --write-table runs/exports/kfix_t3_mf4090.tsv
echo "KFIX_REEXPORT_DONE ${fail}"
