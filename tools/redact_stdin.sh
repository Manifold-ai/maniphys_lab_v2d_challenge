#!/usr/bin/env bash
# 把 stdin 里其他用户的用户名与 home 目录名换成 <其他用户> 再输出（Mac 上、仓库根执行）。名字的来源与 tools/name_leak_check.sh 相同：
# mf4090 与 ml40 上 /home、/lab_data 下属主不是本用户、也不是 root 的目录：目录名与属主，另加环境变量 V2D_EXTRA_NAMES（空格分隔）。
# 系统默认账号 ubuntu 不换（它也是主机名的一部分，name_leak_check.sh 同样放行）。长的名字先换，免得短名字是长名字的一部分时只换掉一半。
# 用途：把同组成员分支上的文档等材料记进 results/ 作证据之前去掉名字（记录要进 git，脱敏约定同 tools/gpu_procs_remote.sh）。
# 取名字的 ssh 用 -n，不吃掉要脱敏的 stdin。取名字失败时退出码 2，不输出原文。Mac 自带 bash 3.2 可跑。
# 用法：<命令> | tools/redact_stdin.sh
#       tools/redact_stdin.sh <文件>...   就地改写这些文件（名字只取一次；10/21 回流第 1 级接管的 119 份记录时加）
set -uo pipefail
all=""
for h in mf4090 ml40; do
  out="$(ssh -n -o BatchMode=yes -o ConnectTimeout=15 "$h" 'me=$(id -un); for d in /home/* /lab_data/*; do [ -d "$d" ] || continue; u=$(stat -c %U "$d"); { [ "$u" = "$me" ] || [ "$u" = root ]; } && continue; echo "$u"; echo "${d##*/}"; done')" \
    || { echo "${h}：取名字失败" >&2; exit 2; }
  all="$all
$out"
done
for n in ${V2D_EXTRA_NAMES:-}; do all="$all
$n"; done
NAMES="$(printf '%s\n' "$all" | grep -v -x -e '' -e ubuntu | sort -u)"
[ -n "$NAMES" ] || { echo "一个名字都没取到" >&2; exit 2; }
NAMES="$NAMES" python3 -c '
import os, sys
names = sorted({n for n in os.environ["NAMES"].split("\n") if n}, key=len, reverse=True)
def scrub(text):
    for n in names:
        text = text.replace(n, "<其他用户>")
    return text
if len(sys.argv) > 1:
    for f in sys.argv[1:]:
        with open(f, encoding="utf-8") as fh:
            text = fh.read()
        new = scrub(text)
        if new != text:
            with open(f, "w", encoding="utf-8") as fh:
                fh.write(new)
            print(f"改写 {f}", file=sys.stderr)
else:
    sys.stdout.write(scrub(sys.stdin.read()))
' "$@"
