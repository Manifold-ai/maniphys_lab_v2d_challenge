#!/usr/bin/env bash
# k-fix 方案 4 第 6 步：用现有 checkpoint 对新参考评测与导出（mf4090 上、仓库根执行，放 tmux 经 scripts/dev/record 落盘）。
# 计划 agent-doc/plan-t3-kfix-2026-10-16.md “方案 4 的执行细则”第 6、7 步。清单（默认 stages/evaluate/exports/kfix_t3_mf4090.tsv）每行：
#   run、步数、参考 parquet（容器内 /repo/... 路径）、后缀、模式。
#   idchk：恒等核对（复核 MINOR）。参考就是这条 run 原来训练用的 parquet，经 eval_playback_override.py 的包装层评 4096 世界；
#          应与原来的 eval_<步数>_w4096.json 一致（kfix_reexport_table.py 比）。只评不导出。
#   kfix：先评 4096 世界（只写指标），再导出 1 个世界（带轨迹，给打包用）。
# 每一步都经 stages/evaluate/fc_export.sh（V2D_EXPORT_PARQUET + V2D_EXPORT_SUFFIX）：它核 checkpoint、NaN 守卫、GPU 占用，并核评测 JSON 里记的
# parquet 就是给的那份。一行失败不停，记下退出码接着做；最后跑 stages/evaluate/kfix_reexport_table.py 汇总并写结果表
# runs/exports/kfix_t3_mf4090.tsv（判据 5 判“换”的、导出齐全的集，格式同 export_chain.sh 的结果表，给 pull_submission.sh select 拉）。
# 最后一行 KFIX_REEXPORT_DONE <失败步数>。
# 用法：V2D_FC_SRC=<8c778f9 副本> stages/evaluate/kfix_reexport.sh [清单]
set -uo pipefail
cd "$(dirname "$0")/../.."
L=${1:-stages/evaluate/exports/kfix_t3_mf4090.tsv}
[ -n "${V2D_FC_SRC:-}" ] || { echo "kfix_reexport: 要设 V2D_FC_SRC" >&2; exit 2; }
[ -f "$L" ] || { echo "kfix_reexport: 没有清单 ${L}" >&2; exit 2; }
echo "== $(hostname) $(date '+%F %T %Z') 来历 $(cat .v2d-source-commit 2>/dev/null)；清单 ${L}（md5 $(md5sum < "$L" | cut -c1-32)）"
fail=0
while IFS=$'\t' read -r run step pq suf mode <&3; do
  [ "$run" = run ] && continue
  echo "=== $(date '+%F %T %Z') ${run} ${step} ${mode} ${suf}"
  V2D_EXPORT_PARQUET=$pq V2D_EXPORT_SUFFIX=$suf V2D_EXPORT_WORLDS=4096 V2D_EXPORT_TRAJ=0 stages/evaluate/fc_export.sh "$run" "$step" < /dev/null; rc=$?
  echo "4096 世界评测 退出码 ${rc}"; [ "$rc" = 0 ] || fail=$((fail + 1))
  if [ "$mode" = kfix ] && [ "$rc" = 0 ]; then
    V2D_EXPORT_PARQUET=$pq V2D_EXPORT_SUFFIX=$suf stages/evaluate/fc_export.sh "$run" "$step" < /dev/null; rc=$?
    echo "1 世界导出 退出码 ${rc}"; [ "$rc" = 0 ] || fail=$((fail + 1))
  fi
done 3< "$L"
python3 stages/evaluate/kfix_reexport_table.py "$L" --write-table runs/exports/kfix_t3_mf4090.tsv
echo "KFIX_REEXPORT_DONE ${fail}"
