#!/usr/bin/env bash
# 在 mf4090 上把 l40n 训练要用的文件打成 3 个 tar（不压缩，tar 保留 assets/urdfs/meshes 这个软链），放进
# runs/hf_src/<标签>/，再由 tools/hf_remote.sh + runs/tools/hf_transfer.py push 经 HF 私有传输仓转到 l40n（数据走 HF，用户 10/13）。
# 只带训练要的部分，不整盘搬（rxzhou 11/02：“数据就别全部dump过去了”）：
#   toolkit.tar  third_party/video_to_data 在 33129dd 的 robotic_grounding/flash_chord（镜像构建上下文）与 robotic_grounding/source（/v2d/assets）
#   fc_src.tar   ~/v2d/fc_src/v040_p185_nfg_oo（r3o 用）与 v040_p185_nfg
#   motion.tar   runs/motion/tier2、runs/motion/tier3（参考轨迹）
# 用法（mf4090 仓库根）：bash deploy/l40n/stage_env_tars.sh <标签>；最后一行 STAGE_OK <标签> 或 STAGE_FAIL <原因>。目标目录已存在就停。
set -uo pipefail
TAG=${1:?用法：stage_env_tars.sh <标签>}
fail() { echo "STAGE_FAIL $*"; exit 1; }
OUT="runs/hf_src/$TAG"
[ -e "$OUT" ] && fail "$OUT 已存在"
TP=third_party/video_to_data
[ "$(git -C "$TP" rev-parse HEAD)" = 33129dd0f2d2dcfd1164d43fd076542660756ed2 ] || fail "官方工具包不在 33129dd"
mkdir -p "$OUT" || fail mkdir
tar -cf "$OUT/toolkit.tar" -C "$TP" robotic_grounding/flash_chord robotic_grounding/source || fail toolkit
tar -cf "$OUT/fc_src.tar" -C "$HOME/v2d/fc_src" v040_p185_nfg_oo v040_p185_nfg || fail fc_src
tar -cf "$OUT/motion.tar" -C runs motion/tier2 motion/tier3 || fail motion
( cd "$OUT" && sha256sum *.tar > TARS.sha256 ) || fail sha
ls -l "$OUT"
echo "STAGE_OK $TAG"
