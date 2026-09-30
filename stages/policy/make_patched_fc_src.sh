#!/usr/bin/env bash
# 生成“v0.4.0 + 上游 #185（8c778f9：方盒支撑面按 size × scale 导入）”的 flash_chord 源码副本，诊断 run 用 V2D_FC_SRC 挂到 /workspace
# （scripts/dev/in-flash-chord）。计划 agent-doc/plan-ep1-ep7-divergence-2026-09-30.md 附录 A 第 4 版。
# 只复制 third_party/video_to_data/robotic_grounding/flash_chord（不含 outputs/、logs/），打 third_party/patches/ 里的补丁，
# 核对打补丁后的 support.py 与上游 8c778f9 的同名文件逐字节相同（sha256），写 SOURCE_V2D.txt。原 checkout 不动；目标已存在就退出。
# 用法（仓库根，训练机上）：stages/policy/make_patched_fc_src.sh <目标目录>
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd -P)"; cd "$ROOT"
DST=${1:?用法：make_patched_fc_src.sh <目标目录>}
[ -e "$DST" ] && { echo "已存在，不覆盖：$DST" >&2; exit 2; }
SRC=third_party/video_to_data/robotic_grounding/flash_chord
PATCH=third_party/patches/flash_chord-v0.4.0-cube-support-scale-8c778f9.patch
WANT=8d82f6008f2310667bef6862dfa3f453d3bdd188c79c7283a26e288a5a19e1c2   # 上游 8c778f905c 的 scene/support.py
HEAD="$(git -C third_party/video_to_data rev-parse --short=7 HEAD)"
[ "$HEAD" = 33129dd ] || { echo "third_party/video_to_data 在 $HEAD，不是 v0.4.0（33129dd）" >&2; exit 2; }
mkdir -p "$DST"
rsync -a --exclude outputs --exclude logs "$SRC/" "$DST/"
# 补丁里的路径是 a/robotic_grounding/flash_chord/src/...：在副本根下用 -p3 去掉前三级
patch -p3 -d "$DST" --dry-run --quiet < "$PATCH"
patch -p3 -d "$DST" --quiet < "$PATCH"
GOT="$(sha256sum "$DST/src/flash_chord/scene/support.py" | cut -d' ' -f1)"
[ "$GOT" = "$WANT" ] || { echo "打补丁后 support.py 的 sha256 $GOT ≠ 上游 8c778f9 的 $WANT" >&2; exit 1; }
printf 'flash_chord v0.4.0（33129dd）+ %s\nscene/support.py sha256 %s，与上游 8c778f905c 相同\n生成于 %s；仓库来历 %s\n' \
  "$PATCH" "$GOT" "$(date '+%F %T %Z')" "$(cat .v2d-source-commit 2>/dev/null || echo unknown)" > "$DST/SOURCE_V2D.txt"
echo "PATCHED_FC_SRC_OK $DST"
