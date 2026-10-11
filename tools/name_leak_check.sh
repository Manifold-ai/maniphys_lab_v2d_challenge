#!/usr/bin/env bash
# 记录进 git 之前的检查：给出的文件里有没有出现其他用户的用户名或 home 目录名。只打印名字的编号、命中次数与行号，不打印名字本身
# （系统默认账号 ubuntu 例外，照名字打印：它也是 ml40 主机名 VM-0-16-ubuntu 的一部分，单独判断）。
# 名字取自 mf4090 与 ml40 上 /home、/lab_data 下属主不是本用户、也不是 root 的目录：目录名与属主（与 tools/gpu_procs_remote.sh 的脱敏范围相同），
# 另加经环境变量 V2D_EXTRA_NAMES 给的名字（空格分隔）。Mac 自带 bash 3.2 可跑（不用 mapfile 与关联数组）。
# 用法（Mac，仓库根）：tools/name_leak_check.sh <文件>...   除 ubuntu 以外有命中时退出码 1。
set -uo pipefail
[ $# -gt 0 ] || { echo "用法：tools/name_leak_check.sh <文件>..." >&2; exit 2; }
all=""
for h in mf4090 ml40; do
  out="$(ssh -o BatchMode=yes -o ConnectTimeout=15 "$h" 'me=$(id -un); for d in /home/* /lab_data/*; do [ -d "$d" ] || continue; u=$(stat -c %U "$d"); { [ "$u" = "$me" ] || [ "$u" = root ]; } && continue; echo "$u"; echo "${d##*/}"; done')" \
    || { echo "${h}：取名字失败" >&2; exit 2; }
  all="$all
$out"
done
for n in ${V2D_EXTRA_NAMES:-}; do all="$all
$n"; done
names="$(printf '%s\n' "$all" | grep -v '^$' | sort -u)"
echo "名字 $(printf '%s\n' "$names" | grep -c .) 个（两台服务器 /home、/lab_data 的目录名与属主，加 V2D_EXTRA_NAMES）"
hit=0
for f in "$@"; do
  [ -f "$f" ] || { echo "${f}：不存在" >&2; exit 2; }
  i=0; line=""
  while IFS= read -r n; do
    i=$((i + 1))
    c="$(grep -o -F -- "$n" "$f" | wc -l | tr -d ' ')"
    [ "$c" -gt 0 ] || continue
    label="#$i"; [ "$n" = ubuntu ] && label=ubuntu
    line="$line ${label}×${c}（行 $(grep -n -F -- "$n" "$f" | cut -d: -f1 | head -5 | tr '\n' ' ' | sed 's/ $//')）"
    [ "$n" = ubuntu ] || hit=1
  done <<< "$names"
  echo "${f}：${line:- 无}"
done
exit $hit
