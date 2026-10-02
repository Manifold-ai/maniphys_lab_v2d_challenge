#!/usr/bin/env bash
# 列出 V2D Track 2 的 12 个 Kaggle 比赛与本账号是否已加入（Mac 上执行，只读：kaggle API 的 competitions list）。
# token 在 ~/.kaggle/access_token（0600），由 kaggle 客户端自己读，不经命令行、不打印。kaggle>=2 要 Python 3.11+，经 uvx 跑。
# 用法（仓库根）：scripts/dev/record submission/kaggle_join_status tools/kaggle_join_status.sh
set -euo pipefail
uvx --quiet --python 3.12 --from 'kaggle>=2' kaggle competitions list --search v2d-challenge-track2 --csv 2>/dev/null | python3 -c '
import csv, sys
rows = [r for r in csv.DictReader(sys.stdin) if "v2d-challenge-track2" in r.get("ref", "")]
print("比赛 %d 个（--search v2d-challenge-track2）" % len(rows))
for r in sorted(rows, key=lambda r: r["ref"]):
    name = r["ref"].rsplit("/", 1)[-1]
    print("  %-40s deadline %s  userHasEntered %s" % (name, r.get("deadline", "?"), r.get("userHasEntered", "?")))
'
