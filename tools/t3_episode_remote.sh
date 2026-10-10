# 服务器上的只读核对：同组成员的 Tier 3 重建产物（/lab_data/<目录>/v2d/tier3/runs/tier3_cari4d）里给定几集的文件、本用户能不能读、元数据内容。
# 经 stdin 送过去执行。只读：不改文件、不进容器。别人的目录名、用户名与 home 目录名一律换成 <其他用户>（同 tools/t3_queue_remote.sh）。
# V2D_T3_SUBDIR 选目录，默认 tier3_cari4d；白名单与 stages/recovery/tier3_pack_remote.sh 相同（计划 agent-doc/plan-t3-pilot-v2-2026-10-10.md）。
# 用法（Mac，仓库根）：scripts/dev/record ops/<名字> ssh ml40 '[V2D_T3_SUBDIR=<目录>] bash -s -- <episode> ...' < tools/t3_episode_remote.sh
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
  SUB="${V2D_T3_SUBDIR:-tier3_cari4d}"
  case "$SUB" in tier3_cari4d|tier3_cari4d_suspect|tier3_cari4d_floor|tier3_cari4d_floor_suspect|tier3_cari4d_f830_floor|tier3_cari4d_f830_floor_suspect) ;;
    *) echo "V2D_T3_SUBDIR 不在白名单里：$SUB"; exit 2 ;;
  esac
  D="${roots[0]}/runs/$SUB"
  echo "## 目录 runs/$SUB"
  echo "## $D 的前两层"
  find "$D" -maxdepth 2 -printf '%M %TF_%TT %s %P\n' | cut -c1-160 | sort -k4 | head -80
  for ep in "$@"; do
    e="$(printf %06d "$ep")"
    echo "## episode $ep"
    for f in "$D/data/chunk-000/episode_$e.parquet" "$D/meta/episode_$e.metadata.json"; do
      if [ -r "$f" ]; then echo "可读 $(stat -c '%s 字节 %y' "$f" | cut -c1-40) sha256 $(sha256sum "$f" | cut -d' ' -f1) ${f#$D/}"
      else echo "读不了或不存在 ${f#$D/}"; fi
    done
    [ -r "$D/meta/episode_$e.metadata.json" ] || continue
    cat "$D/meta/episode_$e.metadata.json"; echo
    # 重建时用的输入网格与地面（元数据里的相对路径，相对 tier3/input）的 md5，用来与官方 Tier 2 目录里的同名文件比对
    for k in mesh ground_plane; do
      rel="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))[sys.argv[2]])' "$D/meta/episode_$e.metadata.json" "$k")"
      f="${roots[0]}/input/$rel"
      echo "输入 $k $( [ -r "$f" ] && md5sum "$f" | cut -d' ' -f1 || echo 读不了或不存在) $rel"
    done
  done
} 2>&1 | red
