"""两份 Tier 3 帧参考目录逐集比内容（要 numpy）。计划 agent-doc/plan-t3b2-2026-10-28.md 判据 T0：npz 文件的 sha256 不同时，分清是数组不同还是只有 zip 封装不同。
每集：两边都有的 episode_XXXXXX.npz，键、dtype、形状、数值逐个比（np.array_equal，不容差）；另报两边 zip 条目的 date_time 与压缩方式。
用法：python stages/evaluate/frefs_equal.py <目录 A> <目录 B> [episode,...]   最后一行 FREFS_EQUAL n（内容全同）或 FREFS_DIFFER k（k 集内容不同，退出码 1）。
"""
import sys
import zipfile
from pathlib import Path

import numpy as np


def main() -> int:
    A, B = Path(sys.argv[1]), Path(sys.argv[2])
    only = {int(x) for x in sys.argv[3].split(",")} if len(sys.argv) > 3 else None
    names = sorted(p.name for p in A.glob("episode_*.npz") if (B / p.name).exists() and (only is None or int(p.stem[-6:]) in only))
    bad = 0
    for n in names:
        with np.load(A / n, allow_pickle=False) as a, np.load(B / n, allow_pickle=False) as b:
            same = sorted(a.files) == sorted(b.files) and all(a[k].dtype == b[k].dtype and a[k].shape == b[k].shape and np.array_equal(a[k], b[k]) for k in a.files)
        za = [(i.filename, i.date_time, i.compress_type) for i in zipfile.ZipFile(A / n).infolist()]
        zb = [(i.filename, i.date_time, i.compress_type) for i in zipfile.ZipFile(B / n).infolist()]
        bad += not same
        print(f"{n}\t内容{'相同' if same else '不同'}\tzip 条目{'相同' if za == zb else '不同'}\tA {za[0][1]} B {zb[0][1]}")
    print(f"FREFS_EQUAL {len(names)}" if bad == 0 else f"FREFS_DIFFER {bad}")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
