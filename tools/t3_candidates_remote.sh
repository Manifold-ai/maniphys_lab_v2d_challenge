# 服务器上的只读快照：同组成员在 ml40 上做的 Tier 3 深度方向静置修正（t3_depth_post.py，分支 track2/tier3-recon 的 5752307）
# 各候选版本的产物与检查结果：版本目录（集数、修改时间）、depth_post.json 的顶层键、画面对齐（dev/depth_diag/align_*.json，
# 29 个常规集逐集中位 IoU 的均值，ep28 不算，口径同 t3_replace_check.py）、门槛日志（gate/logs 的 p2_* 与 oursup_*）、
# 替换判据（t3_replace_check.py）的输出，以及别人 checkout 的最近提交与未提交改动。经 stdin 送过去执行。
# 用途：判断交付版要不要从 best_hm 换成深度修正版（决定记录 agent-doc/decision-t3-delivery-depth-2026-10-13.md）。
# 只读：不改文件、不进容器、不读环境变量；git 用 --no-optional-locks，不刷新别人的 index。别人的目录名、用户名与 home 目录名一律换成 <其他用户>（同 tools/t3_queue_remote.sh）。
# 用法（Mac，仓库根）：scripts/dev/record ops/t3_candidates_ml40_<时间> ssh ml40 'bash -s' < tools/t3_candidates_remote.sh
set -uo pipefail
me="$(id -un)"
mapfile -t roots < <(ls -d /lab_data/*/v2d/tier3 2>/dev/null | grep -v "^/lab_data/$me/")
names=()
for T in "${roots[@]}"; do
  d="${T#/lab_data/}"; d="${d%%/*}"; o="$(stat -c %U "$T")"
  h="$(getent passwd "$o" | cut -d: -f6)"; h="${h##*/}"
  names+=("$d" "$o" "$h")
done
mapfile -t names < <(printf '%s\n' "${names[@]}" | awk 'NF && $0 != "'"$me"'"' | sort -u | awk '{ print length, $0 }' | sort -rn | cut -d' ' -f2-)
red() { local s; s="$(cat)"; for u in "${names[@]}"; do s="${s//$u/<其他用户>}"; done; printf '%s\n' "$s"; }
{
  echo "== $(hostname) $(date '+%F %T %Z')"
  [ ${#roots[@]} = 1 ] || { echo "别的用户的 tier3 目录不是恰好一个：${roots[*]:-无}"; exit 1; }
  T="${roots[0]}"; G="${T%/tier3}/gate"; o="$(stat -c %U "$T")"
  echo "## 别人的脚本类进程（pid、已运行、命令行）"
  ps -u "$o" -o pid=,etime=,args= 2>/dev/null | grep -E '\.sh|\.py|docker' | grep -v grep | cut -c1-300
  echo "## runs/ 下 tier3_cari4d_f830_best* 版本目录（修改时间、parquet 数、名字）"
  for v in "$T"/runs/tier3_cari4d_f830_best*; do
    [ -d "$v" ] || continue
    echo "$(stat -c %y "$v" | cut -c1-19) $(ls "$v"/data/chunk-000/*.parquet 2>/dev/null | wc -l) ${v##*/}"
  done
  echo "## runs/*.depth_post.json（修改时间、字节、顶层键：类型与长度或值）"
  for j in "$T"/runs/*.depth_post.json; do
    [ -f "$j" ] || continue
    echo "# $(stat -c '%y %s' "$j" | cut -c1-19,36-) ${j##*/}"
    python3 - "$j" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
items = d.items() if isinstance(d, dict) else [("(list)", d)]
for k, v in items:
    if isinstance(v, (dict, list)):
        print(f"  {k}: {type(v).__name__} {len(v)}")
    else:
        print(f"  {k}: {str(v)[:200]}")
PY
  done
  echo "## dev/depth_diag/（修改时间、字节、名字）"
  ls -lt --time-style=+%F_%T "$T/dev/depth_diag" 2>/dev/null | sed -n '2,60p' | awk '{ print $6, $5, $7 }'
  echo "## 画面对齐：每个 align_*.json 里各版本 29 个常规集（不含 ep28）逐集 iou_p50 的均值与集数"
  for j in "$T"/dev/depth_diag/align_*.json; do
    [ -f "$j" ] || continue
    echo "# $(stat -c %y "$j" | cut -c1-19) ${j##*/}"
    python3 - "$j" <<'PY'
import json, sys
rows = json.load(open(sys.argv[1]))
if not isinstance(rows, list):
    print("  不是列表，跳过"); sys.exit(0)
rows = [r for r in rows if "ep28" not in str(r.get("episode", ""))]
vers = sorted({k for r in rows for k, v in r.items() if isinstance(v, dict) and "iou_p50" in v})
for v in vers:
    xs = [r[v]["iou_p50"] for r in rows if isinstance(r.get(v), dict) and r[v].get("iou_p50") is not None]
    print(f"  {v}: n={len(xs)} mean_iou_p50={sum(xs) / len(xs):.4f}" if xs else f"  {v}: n=0")
PY
  done
  echo "## 门槛日志 gate/logs（修改时间、字节、名字）"
  ls -lt --time-style=+%F_%T "$G/logs" 2>/dev/null | sed -n '2,60p' | awk '{ print $6, $5, $7 }'
  for f in "$G"/logs/p2_*.txt; do
    [ -f "$f" ] || continue
    echo "# ${f##*/} 最后 6 行"
    tail -n 6 "$f" | cut -c1-300
  done
  echo "## 我们的支撑面重判（oursup_*.txt）：有 gap_mm 的集数、|gap| ≤ 30 mm 的集数、最大 |gap|"
  for f in "$G"/logs/oursup_*.txt; do
    [ -f "$f" ] || continue
    awk -v n="${f##*/}" '/gap_mm=/ { split($0, a, "gap_mm="); split(a[2], b, " "); g = b[1] + 0; if (g < 0) g = -g;
      c++; if (g <= 30) p++; if (g > m) m = g } END { printf "  %s: %d 集，%d 集过，最大 %.1f mm\n", n, c, p, m }' "$f"
  done
  echo "## 替换判据的输出（名字含 replace 的文件，tier3 与 gate 下四层以内）"
  find "$T" "$G" -maxdepth 4 -name '*replace*' -not -path '*/code/*' -not -path '*/repo/*' -printf '%TF_%TH:%TM %s %p\n' 2>/dev/null | sort
  while IFS= read -r f; do
    case "$f" in *.json|*.txt|*.log) echo "# ${f#$T/}"; head -c 3000 "$f"; echo ;; esac
  done < <(find "$T" "$G" -maxdepth 4 -name '*replace*' -not -path '*/code/*' -not -path '*/repo/*' -type f 2>/dev/null | sort)
  echo "## 别人 checkout（tier3/code）的最近 3 个提交与未提交改动"
  gt() { git -c safe.directory="$T/code" --no-optional-locks -C "$T/code" "$@"; }
  gt log -3 --format='%h %ci %s' 2>&1 | cut -c1-200
  gt status --short 2>&1 | head -20
} 2>&1 | red
