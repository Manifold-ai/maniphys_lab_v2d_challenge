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

# ── 搬迁之后删旧副本：bash deploy/ml40/move_repo.sh cleanup-check（只检查）/ --cleanup（检查全过才删）──
# 只删 $OLD.pre-move 这一个目录，~/v2d 下的其他东西不碰。任何一条不符就停，什么都不删。
PRE="${OLD:?}.pre-move"
if [ "$MODE" = cleanup-check ] || [ "$MODE" = --cleanup ]; then
  [ -d "$PRE" ] && [ ! -L "$PRE" ] || die "$PRE 不存在、不是目录或是符号链接"
  [ "$(stat -c %U "$PRE")" = "$(id -un)" ] || die "$PRE 不归 $(id -un)"
  [ -f "$NEW/.v2d-remote-root" ] && [ -f "$NEW/.v2d-source-commit" ] || die "新仓库副本 $NEW 不完整"
  [ ! -e "$OLD" ] || die "$OLD 又出现了，先人工确认"
  busy=""
  for p in $(pgrep -u "$(id -u)" || true); do
    [ "$p" = $$ ] && continue
    for l in /proc/"$p"/cwd /proc/"$p"/fd/*; do
      t=$(readlink "$l" 2>/dev/null) || continue
      case "$t" in "$PRE"|"$PRE"/*) busy+="$p "; break ;; esac
    done
  done
  [ -z "$busy" ] || die "还有进程在用旧副本：$busy"
  for c in $(docker ps -q 2>/dev/null); do
    docker inspect -f '{{range .Mounts}}{{.Source}}{{"\n"}}{{end}}' "$c" | grep -q "^$PRE" && die "容器 $c 挂着旧副本"
  done
  say "没有进程或容器在用旧副本"
  # 旧副本里有、新副本里没有的文件：删了就找不回来，必须为 0（Python 缓存除外：同步的 --delete 会清掉它们）
  missing=$(rsync -a -n --ignore-existing --out-format='%n' "$PRE/" "$NEW/" | grep -v '/$' \
            | grep -vE '(^|/)(__pycache__|\.pytest_cache|\.ruff_cache)/|\.pyc$' || true)
  [ -z "$missing" ] || die "旧副本里有 $(printf '%s\n' "$missing" | wc -l) 个文件新副本里没有：$(printf '%s\n' "$missing" | head -10 | tr '\n' ' ')"
  say "旧副本里的每个文件在新副本里都有（Python 缓存除外）"
  # 两边内容不同的文件：应当都是搬迁后新副本里更新过的（同步来的新代码、追加的日志与结果），列出来逐个核对
  changed=$(rsync -a -n --checksum --existing --out-format='%n' "$PRE/" "$NEW/" | grep -v '/$' || true)
  say "内容不同的文件：$(printf '%s' "$changed" | grep -c . || true) 个"
  printf '%s\n' "$changed" | grep . | sed 's/^/    /' || true
  say "待删：$PRE  $(du -sh "$PRE" | cut -f1)"
  [ "$MODE" = --cleanup ] || { say "只做了检查。确认后用 --cleanup 删除"; exit 0; }
  rm -rf --one-file-system "${PRE:?}"
  say "已删除 $PRE；系统盘：$(df -h --output=used,avail,pcent / | tail -1)"
  exit 0
fi

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
