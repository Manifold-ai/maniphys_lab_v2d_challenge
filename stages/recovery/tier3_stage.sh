#!/usr/bin/env bash
# 把 ml40 上同组成员 Tier 3 重建产物里的几集转到 mf4090，拼进档目录 runs/tier3/root（Mac 上、仓库根执行，Mac 只转发）。
# 计划 agent-doc/plan-t3-pilot-2026-10-09.md 第 3 节。
#   1. mf4090 上建 runs/tier3/incoming/<标签>/（已存在就拒绝：同一标签只转一次）
#   2. ssh ml40 经 stdin 跑 stages/recovery/tier3_pack_remote.sh（自己找目录，不出现别人的名字），tar 流经 Mac 管道在 mf4090 上解开
#   3. mf4090 上列出解出文件的 sha256 与部署版本，再跑 stages/recovery/tier3_root.py（要先同步到 mf4090）
# 用法：stages/recovery/tier3_stage.sh <标签> <集>...      例：stages/recovery/tier3_stage.sh t3p_1009 8 24
#   落盘：scripts/dev/record t3p/stage_mf4090 stages/recovery/tier3_stage.sh t3p_1009 8 24
set -euo pipefail
cd "$(dirname "$0")/../.."
TAG=${1:?用法：tier3_stage.sh <标签> <集>...}; shift
[ $# -ge 1 ] || { echo "tier3_stage: 要至少一集" >&2; exit 2; }
[[ $TAG =~ ^[A-Za-z0-9_-]+$ ]] || { echo "tier3_stage: 标签非法：$TAG" >&2; exit 2; }
for ep in "$@"; do [[ $ep =~ ^[0-9]+$ ]] || { echo "tier3_stage: 集号非法：$ep" >&2; exit 2; }; done
R='~/v2d/maniphys_lab_v2d_challenge'; IN="runs/tier3/incoming/$TAG"
ssh -o BatchMode=yes mf4090 "cd $R && [ ! -e $IN ] && mkdir -p $IN" || { echo "tier3_stage: mf4090 上 $IN 已存在或建不了" >&2; exit 1; }
ssh -o BatchMode=yes ml40 "bash -s -- $*" < stages/recovery/tier3_pack_remote.sh | ssh -o BatchMode=yes mf4090 "cd $R && tar -xf - -C $IN"
ssh -o BatchMode=yes mf4090 "cd $R && echo \"== \$(hostname) \$(date '+%F %T %Z') 来历 \$(cat .v2d-source-commit)\" && (cd $IN && find . -type f | sort | xargs sha256sum) && echo \"部署版本 \$(cat $IN/DEPLOYED)\" && python3 stages/recovery/tier3_root.py $IN"
