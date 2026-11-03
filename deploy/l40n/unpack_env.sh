#!/usr/bin/env bash
# 在 l40n 仓库根把 HF 标签 l40n_env_1102 下载下来的 3 个 tar 按 TARS.sha256 核对后解到与 mf4090 相同的相对位置
# （打包见 deploy/l40n/stage_env_tars.sh，交接 agent-doc/handoff-l40n-env-2026-11-02.md）：
#   toolkit.tar → third_party/video_to_data/（robotic_grounding/flash_chord 与 robotic_grounding/source；同步时受 P 规则保护）
#   fc_src.tar  → ~/v2d/fc_src/（v040_p185_nfg_oo、v040_p185_nfg）
#   motion.tar  → runs/（motion/tier2、motion/tier3）
# 这里没有官方仓库的 .git，fc_run.sh 记录里的 upstream 会写 unknown；版本由 stage_env_tars.sh 核过（33129dd）。
# 目标已存在就停，不覆盖。用法：bash deploy/l40n/unpack_env.sh <下载目录>；最后一行 UNPACK_OK 或 UNPACK_FAIL <原因>。
set -uo pipefail
IN=${1:?用法：unpack_env.sh <下载目录>}
fail() { echo "UNPACK_FAIL $*"; exit 1; }
D="$IN/runs/hf_src/l40n_env_1102"
[ -f "$D/TARS.sha256" ] || fail "缺 $D/TARS.sha256"
( cd "$D" && sha256sum -c TARS.sha256 ) || fail sha256
for t in third_party/video_to_data/robotic_grounding "$HOME/v2d/fc_src/v040_p185_nfg_oo" "$HOME/v2d/fc_src/v040_p185_nfg" runs/motion/tier2 runs/motion/tier3; do
  [ -e "$t" ] && fail "$t 已存在"
done
mkdir -p third_party/video_to_data "$HOME/v2d/fc_src" runs || fail mkdir
tar -xf "$D/toolkit.tar" -C third_party/video_to_data || fail toolkit
tar -xf "$D/fc_src.tar" -C "$HOME/v2d/fc_src" || fail fc_src
tar -xf "$D/motion.tar" -C runs || fail motion
du -sh third_party/video_to_data "$HOME/v2d/fc_src" runs/motion/tier2 runs/motion/tier3
echo UNPACK_OK
