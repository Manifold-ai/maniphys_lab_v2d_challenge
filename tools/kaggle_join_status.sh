#!/usr/bin/env bash
# 列出 V2D Track 2 的 12 个 Kaggle 比赛与本账号是否已加入（Mac 上执行，只读：kaggle API 的 competitions list）。
# token 在 ~/.kaggle/access_token（0600），由 kaggle 客户端自己读，不经命令行、不打印。kaggle>=2 要 Python 3.11+，默认经 uvx 跑。
# 校园网下 uvx 拉不到 PyPI（Connection reset）：这时用 KAGGLE_BIN 指向已有的 kaggle>=2 客户端（例如 uv 缓存里的那个）。
# 取不到 12 个比赛就退出码 1：10/15 曾因 uvx 连不上、错误被吞，输出了“比赛 0 个”。
# 用法（仓库根）：[KAGGLE_BIN=<kaggle 客户端>] scripts/dev/record submission/kaggle_join_status tools/kaggle_join_status.sh
set -euo pipefail
if [ -n "${KAGGLE_BIN:-}" ]; then
  csv="$("$KAGGLE_BIN" competitions list --search v2d-challenge-track2 --csv)"
else
  csv="$(uvx --quiet --python 3.12 --from 'kaggle>=2' kaggle competitions list --search v2d-challenge-track2 --csv)"
fi
printf '%s\n' "$csv" | python3 -c '
import csv, sys
rows = [r for r in csv.DictReader(sys.stdin) if "v2d-challenge-track2" in r.get("ref", "")]
print("比赛 %d 个（--search v2d-challenge-track2）" % len(rows))
for r in sorted(rows, key=lambda r: r["ref"]):
    name = r["ref"].rsplit("/", 1)[-1]
    print("  %-40s deadline %s  userHasEntered %s" % (name, r.get("deadline", "?"), r.get("userHasEntered", "?")))
sys.exit(0 if len(rows) == 12 else 1)
'
