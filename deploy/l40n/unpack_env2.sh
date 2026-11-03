#!/usr/bin/env bash
# 在 l40n 仓库根解第二批（HF 标签 l40n_env2_1102，打包见 stage_env2_tars.sh），并按 agent-doc/plan-t2auc3-2026-11-02.md 第 1 节验收第 1 条
# 把工具包恢复成 33129dd 的干净工作树：第一批只带了 robotic_grounding/flash_chord 与 source，放进 .git 后其余被跟踪的文件
# 算删除，所以把这些文件从 33129dd 取出来（只取删除的，LFS 大文件留指针；已在的文件不动）。
# 用法：bash deploy/l40n/unpack_env2.sh <下载目录>；最后一行 UNPACK2_OK 或 UNPACK2_FAIL <原因>。目标已存在就停。
set -uo pipefail
IN=${1:?用法：unpack_env2.sh <下载目录>}
fail() { echo "UNPACK2_FAIL $*"; exit 1; }
D="$IN/runs/hf_src/l40n_env2_1102"
TP=third_party/video_to_data
[ -f "$D/TARS.sha256" ] || fail "缺 $D/TARS.sha256"
( cd "$D" && sha256sum -c TARS.sha256 ) || fail sha256
for t in "$TP/.git" "$HOME/v2d/fc_src/fc_8c778f9" runs/motion_src/tier2 runs/motion_src/tier3 runs/motion_src/tier3_gb4 runs/motion/tier3_gb4; do
  [ -e "$t" ] && fail "$t 已存在"
done
tar -xf "$D/git.tar" -C "$TP" || fail git
tar -xf "$D/fc8.tar" -C "$HOME/v2d/fc_src" || fail fc8
tar -xf "$D/msrc.tar" -C runs || fail msrc
tar -xf "$D/gb4.tar" -C runs || fail gb4
[ "$(git -C "$TP" rev-parse HEAD)" = 33129dd0f2d2dcfd1164d43fd076542660756ed2 ] || fail "HEAD 不是 33129dd"
git lfs install --skip-smudge >/dev/null || fail git-lfs   # 全局 filter 配置：已在的大文件按内容算指针比对，不下载
# 只恢复被标成删除的文件（flash_chord、source 以外的被跟踪文件）；跳过 LFS 下载，大文件留指针（训练用不到它们）
git -C "$TP" ls-files -d -z | GIT_LFS_SKIP_SMUDGE=1 xargs -0 -r git -C "$TP" checkout -- || fail checkout
dirty="$(git -C "$TP" status --porcelain --untracked-files=no)"
[ -z "$dirty" ] || { printf '%s\n' "$dirty" | head -20; fail "工作树不干净（$(printf '%s\n' "$dirty" | wc -l) 行）"; }
du -sh "$TP" "$HOME/v2d/fc_src" runs/motion_src runs/motion
echo UNPACK2_OK
