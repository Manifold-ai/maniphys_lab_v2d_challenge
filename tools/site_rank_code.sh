#!/usr/bin/env bash
# 官网排行榜怎么排名次：抓官网的 leaderboard.js 与数据仓 MVerghese/v2d-leaderboard-data 的 aggregator，打印 sha256 和排名相关的几段原文。
# 只读公开网页（Mac 上跑，经 scripts/dev/record 落盘）。下载的文件放 mktemp 目录，不执行。
# 用法：tools/site_rank_code.sh
set -euo pipefail
T=$(mktemp -d)
trap 'rm -rf "$T"' EXIT
curl -sf -m 30 -o "$T/leaderboard.js" https://nvidia-isaac.github.io/video_to_data/v2d_challenge/leaderboard.js
curl -sf -m 30 -o "$T/page.html" https://nvidia-isaac.github.io/video_to_data/v2d_challenge/
curl -sf -m 30 -o "$T/leaderboard.json" "https://raw.githubusercontent.com/MVerghese/v2d-leaderboard-data/main/leaderboard.json?v=$(date +%s)"
gh api repos/MVerghese/v2d-leaderboard-data/contents/aggregator/v2d_aggregate.py --jq .content | base64 -d > "$T/v2d_aggregate.py"
gh api repos/MVerghese/v2d-leaderboard-data --jq '"数据仓：" + .full_name + "，private " + (.private|tostring) + "，最近推送 " + .pushed_at + "，说明：" + .description'
for f in leaderboard.js leaderboard.json v2d_aggregate.py; do
  echo "sha256 $(shasum -a 256 "$T/$f" | cut -d' ' -f1)  $f"
done
echo "== 官网页面的数据来源"
grep -o 'data-src="[^"]*"' "$T/page.html"
echo "== leaderboard.js：同分怎么排（compare）与表里的名次（canonicalRanks）"
awk '/function compare\(a, b, key, direction\)/,/^  }$/' "$T/leaderboard.js"
awk '/function canonicalRanks\(track, metric\)/,/^  }$/' "$T/leaderboard.js"
echo "== v2d_aggregate.py：数据里的 rank 字段"
awk '/# Default order: best on the track/,/entry\["rank"\] = position/' "$T/v2d_aggregate.py"
echo "== leaderboard.json 的生成时间"
python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(d.get('generated_at'), d.get('source'))" "$T/leaderboard.json"
echo "SITE_RANK_CODE_DONE"
