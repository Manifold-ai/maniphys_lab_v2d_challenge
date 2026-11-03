#!/usr/bin/env bash
# l40n 第二批（在 mf4090 仓库根执行；第一批见 stage_env_tars.sh）。第一批之后按接入盘点补的、链上要的东西：
#   git.tar     third_party/video_to_data/.git（33129dd）：fc_src_check.py 要对工具包跑 git rev-parse 与工作树核对
#   fc8.tar     ~/v2d/fc_src/fc_8c778f9：arm_var_chain.sh 要求它在
#   msrc.tar    runs/motion_src/tier2、tier3、tier3_gb4（v2d_meta.json 等，arm_var_chain.sh 按序列核）
#   gb4.tar     runs/motion/tier3_gb4（Tier 3 gb4 参考）
# 用法：bash stage_env2_tars.sh <标签>；最后一行 STAGE_OK <标签> 或 STAGE_FAIL <原因>。目标目录已存在就停。
set -uo pipefail
TAG=${1:?用法：stage_env2_tars.sh <标签>}
fail() { echo "STAGE_FAIL $*"; exit 1; }
OUT="runs/hf_src/$TAG"
[ -e "$OUT" ] && fail "$OUT 已存在"
TP=third_party/video_to_data
[ "$(git -C "$TP" rev-parse HEAD)" = 33129dd0f2d2dcfd1164d43fd076542660756ed2 ] || fail "官方工具包不在 33129dd"
mkdir -p "$OUT" || fail mkdir
tar -cf "$OUT/git.tar" -C "$TP" .git || fail git
tar -cf "$OUT/fc8.tar" -C "$HOME/v2d/fc_src" fc_8c778f9 || fail fc8
tar -cf "$OUT/msrc.tar" -C runs motion_src/tier2 motion_src/tier3 motion_src/tier3_gb4 || fail msrc
tar -cf "$OUT/gb4.tar" -C runs motion/tier3_gb4 || fail gb4
( cd "$OUT" && sha256sum *.tar > TARS.sha256 ) || fail sha
ls -l "$OUT"
echo "STAGE_OK $TAG"
