# 在 ml40 上（经 stdin 执行）把同组成员 Tier 3 重建产物里指定几集的 parquet、元数据与部署版本打成 tar，写到 stdout。
# 计划 agent-doc/plan-t3-pilot-2026-10-09.md 第 3 节。由 stages/recovery/tier3_stage.sh 调用，经 Mac 管道转给 mf4090。
# 目录自己找：/lab_data/<目录>/v2d/tier3 里不属于本用户的，必须恰好一个。命令行、报错与 tar 里都不出现别人的名字（tar 里只有相对路径）。
# 只读。任何一个文件缺或读不了就退出码 1，不写 tar（stdout 为空，对端解包会失败）。
# 报错只用相对路径；tar 自己的 stderr 丢掉、只报退出码（它的报错会带绝对路径，也就带出别人的目录名；审查 M2）。
# V2D_T3_SUBDIR 选目录：tier3_cari4d（默认，通过剪影检查的集）或 tier3_cari4d_suspect（没通过的集，只用于只读分析，如 t3_float_facts.py）；
#   以及同组成员 10/9 晚另写的两版校正 tier3_cari4d_floor、tier3_cari4d_f830_floor 和各自的 _suspect（计划 agent-doc/plan-t3-pilot-v2-2026-10-10.md），
#   10/11 的 tier3_cari4d_f830_simreg 与 _suspect（人体随场景缩放、第二机位 5 集配准到主机位；计划 agent-doc/plan-t3-simreg-p2-2026-10-11.md）。
#   白名单与 tools/t3_episode_remote.sh 相同，改一处要两处一起改。
# 用法（Mac，仓库根）：ssh ml40 'bash -s -- <集>...' < stages/recovery/tier3_pack_remote.sh | ...
set -uo pipefail
[ $# -ge 1 ] || { echo "tier3_pack_remote: 要至少一集" >&2; exit 2; }
me="$(id -un)"
mapfile -t roots < <(ls -d /lab_data/*/v2d/tier3 2>/dev/null | grep -v "^/lab_data/$me/")
[ ${#roots[@]} = 1 ] || { echo "tier3_pack_remote: 别的用户的 tier3 目录有 ${#roots[@]} 个，应当恰好一个" >&2; exit 1; }
SUB="${V2D_T3_SUBDIR:-tier3_cari4d}"
case "$SUB" in tier3_cari4d|tier3_cari4d_suspect|tier3_cari4d_floor|tier3_cari4d_floor_suspect|tier3_cari4d_f830_floor|tier3_cari4d_f830_floor_suspect|tier3_cari4d_f830_simreg|tier3_cari4d_f830_simreg_suspect) ;;
  *) echo "tier3_pack_remote: V2D_T3_SUBDIR 不在白名单里：$SUB" >&2; exit 2 ;;
esac
T="${roots[0]}"; D="$T/runs/$SUB"
files=()
for ep in "$@"; do
  [[ $ep =~ ^[0-9]+$ ]] || { echo "tier3_pack_remote: 集号非法：$ep" >&2; exit 2; }
  e="$(printf %06d "$ep")"
  for f in "data/chunk-000/episode_$e.parquet" "meta/episode_$e.metadata.json"; do
    [ -r "$D/$f" ] || { echo "tier3_pack_remote: 读不了 runs/$SUB/$f" >&2; exit 1; }
    files+=("$f")
  done
done
[ -r "$T/code/DEPLOYED" ] || { echo "tier3_pack_remote: 读不了 code/DEPLOYED" >&2; exit 1; }
tar -cf - -C "$T/code" DEPLOYED -C "$D" "${files[@]}" 2>/dev/null || { echo "tier3_pack_remote: tar 失败（退出码 $?）" >&2; exit 1; }
