#!/usr/bin/env bash
# 查组委会账号 Nvidia-V2D-Challenge 是不是代码仓库的协作者（Mac 上、仓库根执行，只读 GitHub API）。
# 规则要求每份提交里的 commit 链接组委会能打开；仓库私有，要靠协作者权限。204 表示是，404 表示不是。
# 用法：scripts/dev/record ops/collab_check_nvidia_<时间> tools/collab_check.sh
set -uo pipefail
R=$(git remote get-url origin | sed -E 's#(git@github.com:|https://github.com/)##; s#\.git$##')
echo "仓库 $R"
gh api "repos/$R" --jq '"可见性 " + .visibility + "，本账号 admin 权限 " + (.permissions.admin|tostring) + "，maintain 权限 " + (.permissions.maintain|tostring)'
echo "查询 Nvidia-V2D-Challenge 是不是协作者（GET repos/$R/collaborators/Nvidia-V2D-Challenge）：$(gh api "repos/$R/collaborators/Nvidia-V2D-Challenge" -i 2>&1 | head -1)"
