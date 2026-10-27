#!/usr/bin/env bash
# t3fix 的复制清单生成（训练机上执行；只读：只 find、stat，不写她的目录）。计划 agent-doc/plan-t3fix-2026-10-27.md 第 1 节 D1、第 0 节第 8 条。
# 在 T3R_SRC（另一位成员的 v2d 目录，运行时由调用方给，仓库里不写）下列出 gb5 交付层 30 集做 A、C 与重跑 dyn7 之后各步要的文件，打成 t3r_copy.sh 的清单：
#   类别 in、源（相对于 T3R_SRC）、目标（相对于我们的 t3recon 根，放在 t3fx/ 下，路径去掉开头的 tier3/）。
# 列的是：input 的 meta、mesh、ground_plane；runs 下 gb5_best 的选择表、dr2s 与 dyn7 两层（含 _suspect）及它们的 json 记录、dr2s 的物理检查、floor、support；
# 各集转换目录（convert*_gb5/<集>/，不要 *.pt）；各集掩码 masks_k0.h5（按选择表的 convert 找 work 目录，同 t3_align_check.WORK）；dev/walls。cari4d 大目录不拷。
# 用法：T3R_SRC=<她的目录> stages/recovery/t3r_fix_files.sh > <清单>   缺掩码就停（退出码 1）。
set -euo pipefail
SRC=${T3R_SRC:?要设 T3R_SRC}
T=tier3
cd "$SRC"
emit() { while IFS= read -r f; do printf 'in\t%s\tt3fx/%s\n' "$f" "${f#"$T"/}"; done; }
{
  find -L "$T/input/meta" "$T/input/mesh" "$T/input/ground_plane" -type f
  find -L "$T/runs" -maxdepth 1 -type f \( -name 'tier3_cari4d_gb5_best.selection.json' -o -name 'tier3_cari4d_gb5_best_dr2s.*json' -o -name 'tier3_cari4d_gb5_best_dr2s_dyn7.*json' \)
  for v in tier3_cari4d_gb5_best_dr2s tier3_cari4d_gb5_best_dr2s_suspect tier3_cari4d_gb5_best_dr2s_dyn7 tier3_cari4d_gb5_best_dr2s_dyn7_suspect; do
    [ -d "$T/runs/$v" ] && find -L "$T/runs/$v" -type f
  done
  [ -d "$T/runs/physics/tier3_cari4d_gb5_best_dr2s" ] && find -L "$T/runs/physics/tier3_cari4d_gb5_best_dr2s" -type f
  find -L "$T/runs/floor" -maxdepth 1 -type f
  [ -d "$T/runs/support" ] && find -L "$T/runs/support" -type f
  [ -d "$T/dev/walls" ] && find -L "$T/dev/walls" -type f
  python3 - "$T/runs/tier3_cari4d_gb5_best.selection.json" <<'EOF'
import json, sys
from pathlib import Path
work = {"convert": "work", "convert_v2": "work_v2", "convert_fp": "work_fp", "convert_pivot": "work_fp"}
sel = Path(sys.argv[1])
runs = sel.parent
for r in json.loads(sel.read_text()):
    conv, name = r["convert"], r["episode"]
    base = conv.removesuffix("_gb5").removesuffix("_gb4").removesuffix("_gb3")
    for p in sorted((runs / conv / name).rglob("*")):
        if p.is_file() and p.suffix != ".pt":
            print(p)
    m = runs / work[base] / name / "masks_k0.h5"
    if not m.is_file():
        sys.exit(f"缺掩码：{m}")
    print(m)
EOF
} | sort -u | emit
