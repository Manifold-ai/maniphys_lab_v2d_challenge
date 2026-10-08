#!/usr/bin/env bash
# Tier 1 逐条选的打分、选择与打包（ml40、仓库根执行）。计划 agent-doc/plan-t1-per-episode-select-2026-10-08.md 第 2 版。
# 这台机器上的仓库是 rsync 副本，pack_tier.sh 的守卫不在这里跑，所以这里自己核（审查第 1 条）：
#   .v2d-source-commit 是 --commit-url 那个 commit、没有 -dirty / -syncing；kit zip 的 sha256 是 0f2f9f4b…；CSV 已存在就拒绝。
# 用法：stages/evaluate/select_t1.sh <https://github.com/…/commit/<sha>> [--no-pack]
# 输入：runs/select_t1/cand/<run>/（stage_t1_candidates.sh 集中来的候选）、runs/select_t1/tables/*.tsv（导出链结果表）、
#       stages/evaluate/exports/{mf4090,ml40}.tsv（现在交的 30 条）、runs/kit/update_0f2f9f4b/（官方 kit）、runs/kitdeps/（kit 依赖）。
# 输出：results/select_t1/select_1008.txt（record）、results/select_t1/scores_1008.json、results/select_t1/t1_select_1008.tsv、
#       runs/submission/csv/track2_tier1_select_1008.csv（不进 git）。
set -uo pipefail
cd "$(dirname "$0")/../.."
die() { echo "select_t1: $*" >&2; exit "${2:-2}"; }
URL=${1:?commit URL}; NOPACK=${2:-}
[[ $URL =~ ^https://github\.com/Manifold-ai/maniphys_lab_v2d_challenge/commit/([0-9a-f]{40})$ ]] || die "commit URL 格式不对：$URL"
SHA=${BASH_REMATCH[1]}
SRC="$(cat .v2d-source-commit 2>/dev/null)"
[[ $SRC == "${SHA:0:12}" ]] || die "这里的来历是 '$SRC'，不是 ${SHA:0:12}（或带 -dirty / -syncing）：先提交、推送、再同步"
KIT=runs/kit/update_0f2f9f4b
[ "$(sha256sum $KIT/v2d_submission_kit.zip | cut -d' ' -f1)" = 0f2f9f4bb01082a48ab684750cbcbddd985c2de7031847928ae124e53fa605d7 ] || die "kit zip 不是 0f2f9f4b"
CSV=runs/submission/csv/track2_tier1_select_1008.csv
PACK=(--pack /repo/$CSV)
[ "$NOPACK" = --no-pack ] && PACK=()
[ -n "${PACK[*]:-}" ] && [ -e "$CSV" ] && die "$CSV 已存在"
mkdir -p results/select_t1 runs/submission/csv
scripts/dev/record select_t1/select_1008 scripts/dev/in-flash-chord "cd /repo && PYTHONPATH=/repo/runs/kitdeps python stages/evaluate/select_t1.py \
  --cand runs/select_t1/cand --kit $KIT/v2d_submission_kit --dataset-root data/challenge --commit-url $URL \
  --current stages/evaluate/exports/mf4090.tsv stages/evaluate/exports/ml40.tsv --sha-tables runs/select_t1/tables/*.tsv \
  --out-json results/select_t1/scores_1008.json --out-tsv results/select_t1/t1_select_1008.tsv ${PACK[*]:-}"
