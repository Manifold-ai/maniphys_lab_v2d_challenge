"""导出那 1 局里仿真物体与参考物体的逐帧位置误差（训练机上经 scripts/dev/in-flash-chord 在容器里跑，只用 CPU，只读导出 parquet；只报不判）。
起因：agent-doc/plan-t3hand-2026-10-27.md 复核 BLOCKER 1：P1 的前提是 ep16 在“手到晚”的那段（第 126–137 帧）就丢，要用现有导出核。
对每份导出：按 object_onset_rollout.py 的读法取最小 environment_id、第一个 object_body_id、按 step 排序；
误差 = |achieved_position − reference_position|；报首次 > 5 / 10 / 20 cm 的帧、若干标记帧的误差，以及 --range a:b:s 里每 s 帧一行。
用法（容器内）：python /repo/stages/evaluate/rollout_object_error.py [--range 100:320:10] <导出 parquet>...   最后一行 ROLLOUT_OBJECT_ERROR_DONE
"""
import argparse
import sys

import numpy as np
import pyarrow.parquet as pq

POS = ("achieved_position_x", "achieved_position_y", "achieved_position_z")
REF = ("reference_position_x", "reference_position_y", "reference_position_z")
MARKS = (0, 50, 100, 120, 130, 140, 150, 175, 200, 250, 300, 400, 500, 600, 800)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--range", default=None, help="a:b:s，另按这个范围每 s 帧打一行")
    ap.add_argument("parquet", nargs="+")
    a = ap.parse_args()
    for path in a.parquet:
        t = pq.read_table(path)
        d = t.to_pydict()
        if not all(c in d for c in POS + REF + ("step",)):
            print(f"{path}：列不对，有 {t.column_names}")
            return 2
        keep = np.ones(t.num_rows, dtype=bool)
        if "environment_id" in d:
            keep &= np.asarray(d["environment_id"]) == min(d["environment_id"])
        if "object_body_id" in d:
            keep &= np.asarray(d["object_body_id"]) == d["object_body_id"][0]
        order = np.argsort(np.asarray(d["step"]), kind="stable")
        order = order[keep[order]]
        p = np.stack([np.asarray(d[c], dtype=float)[order] for c in POS], axis=1)
        r = np.stack([np.asarray(d[c], dtype=float)[order] for c in REF], axis=1)
        err = np.linalg.norm(p - r, axis=1)
        firsts = {th: (int(np.flatnonzero(err > th / 100)[0]) if (err > th / 100).any() else None) for th in (5, 10, 20)}
        print(f"{path}：{len(err)} 帧；误差首次 > 5 / 10 / 20 cm 的帧 {firsts[5]} / {firsts[10]} / {firsts[20]}；误差中位 {np.median(err) * 100:.1f} cm、最大 {err.max() * 100:.1f} cm（第 {int(err.argmax())} 帧）")
        print("  帧\t误差 cm\t参考相对第 0 帧的平移 m")
        rows = [f for f in MARKS if f < len(err)]
        if a.range:
            s0, s1, st = (int(x) for x in a.range.split(":"))
            rows = sorted(set(rows) | set(range(s0, min(s1, len(err)), st)))
        for f in rows:
            print(f"  {f}\t{err[f] * 100:.1f}\t{np.linalg.norm(r[f] - r[0]):.3f}")
    print("ROLLOUT_OBJECT_ERROR_DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
