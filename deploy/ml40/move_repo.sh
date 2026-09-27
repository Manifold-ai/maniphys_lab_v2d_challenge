#!/usr/bin/env bash
# ml40：把仓库副本从系统盘（~/v2d/maniphys_lab_v2d_challenge）搬到 /lab_data/rxzhou/v2d/（数据盘）。
# 以 rxzhou 在 ml40 上执行，不需要 sudo。批量训练每条 run 约 5.8 GB checkpoint，系统盘（150 GB、共用）放不下。
#
# 用法：bash deploy/ml40/move_repo.sh            # 只检查：大小、有没有进程或容器在用旧目录
#       bash deploy/ml40/move_repo.sh --apply    # 拷贝 → 按校验和比对（必须零差异）→ 旧目录改名为 .pre-move（不删）
# 之后在 Mac 上把 .env.ml40 的 V2D_REMOTE 改成新路径，再 V2D_DRYRUN=1 V2D_ENV=ml40 scripts/dev/remote 看同步清单。
# 旧目录不建符号链接：还引用旧路径的东西应当立刻报错，而不是悄悄写回系统盘。确认无误后再手工删 .pre-move。
set -euo pipefail
OLD=$HOME/v2d/maniphys_lab_v2d_challenge
NEW=/lab_data/rxzhou/v2d/maniphys_lab_v2d_challenge
MODE=${1:-check}
say() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }
die() { say "中止：$*"; exit 1; }

[ -f "$OLD/.v2d-remote-root" ] || die "$OLD 不是 scripts/dev/init-remote 标记过的仓库副本"
[ ! -e "$NEW" ] || die "$NEW 已存在"
[ -w /lab_data/rxzhou ] || die "/lab_data/rxzhou 不可写"
busy=""
for p in $(pgrep -u "$(id -u)" || true); do
  [ "$p" = $$ ] && continue
  d=$(readlink "/proc/$p/cwd" 2>/dev/null || true)
  case "$d" in "$OLD"|"$OLD"/*) busy+="$p($(tr '\0' ' ' < "/proc/$p/cmdline" 2>/dev/null | cut -c1-60)) ";; esac
done
[ -z "$busy" ] || die "还有进程的工作目录在旧仓库里：$busy"
[ -z "$(docker ps -q 2>/dev/null)" ] || die "有运行中的容器（它们可能挂着旧路径）"
say "旧目录 $(du -sh "$OLD" | cut -f1)，/lab_data 可用 $(df -h --output=avail /lab_data | tail -1 | tr -d ' ')"
[ "$MODE" = --apply ] || { say "只做了检查。确认后加 --apply"; exit 0; }

mkdir -p "$(dirname "$NEW")"
say "拷贝 $OLD → $NEW"
rsync -aH "$OLD/" "$NEW/"
say "按校验和比对"
diffs=$(rsync -aHn --checksum --delete --itemize-changes "$OLD/" "$NEW/" | wc -l)
[ "$diffs" = 0 ] || die "拷贝后仍有 $diffs 处差异，旧目录保持原样"
mv "$OLD" "$OLD.pre-move"
say "完成：新仓库副本 $NEW；旧目录改名为 $OLD.pre-move（确认无误后手工删除）"
