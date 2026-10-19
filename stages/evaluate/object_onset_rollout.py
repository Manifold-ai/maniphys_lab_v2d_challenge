"""导出那 1 局里物体离开初始位姿的时刻（训练机上经 scripts/dev/in-flash-chord 在容器里跑，只用 CPU，只读导出 parquet；只报不判）。
起因：agent-doc/plan-t2st-2026-10-19.md 执行记录：Tier 2 ep25 只训了 409.6 万步的冒烟策略，也把瓶子带离了 1.1–1.3 m。
机器人还没学会走到桌边，瓶子是不是自己先掉了？这里量导出轨迹里物体相对第 0 帧的平移与转角随帧的变化：
第一次平移超过 --pos-cm 或转角超过 --rot-deg 的帧，以及若干帧上的平移、转角与高度变化。门槛只用于描述，不进任何方法。
导出 parquet 的列：pos_x/pos_y/pos_z 与 quat_x/quat_y/quat_z/quat_w（同提交 CSV）；有 world 列时只取第 0 个世界，有 body 列时只取第一个部件。
用法（容器内）：python /repo/stages/evaluate/object_onset_rollout.py [--pos-cm 3] [--rot-deg 10] <导出 parquet>...   最后一行 OBJECT_ONSET_DONE
"""
import argparse
import sys

import numpy as np
import pyarrow.parquet as pq

POS = ("pos_x", "pos_y", "pos_z")
QUAT = ("quat_x", "quat_y", "quat_z", "quat_w")
MARKS = (0, 5, 10, 25, 50, 100, 150, 200, 300, 400, 600, 800)


def angle_deg(q0: np.ndarray, q: np.ndarray) -> np.ndarray:
    d = np.abs(np.sum(q * q0[None, :], axis=1)) / (np.linalg.norm(q, axis=1) * np.linalg.norm(q0))
    return np.degrees(2 * np.arccos(np.clip(d, 0.0, 1.0)))


def one(path: str, pos_cm: float, rot_deg: float) -> None:
    t = pq.read_table(path)
    cols = t.column_names
    if not all(c in cols for c in POS + QUAT):
        print(f"{path}：列不对，有 {cols}")
        sys.exit(2)
    d = t.to_pydict()
    keep = np.ones(t.num_rows, dtype=bool)
    for c in ("world", "world_index", "env"):
        if c in d:
            keep &= np.asarray(d[c]) == min(d[c])
    for c in ("body", "body_index", "part"):
        if c in d:
            keep &= np.asarray(d[c]) == d[c][0]
    order = np.arange(t.num_rows)
    for c in ("frame", "step", "frame_index"):
        if c in d:
            order = np.argsort(np.asarray(d[c]), kind="stable")
            break
    order = order[keep[order]]
    p = np.stack([np.asarray(d[c], dtype=float)[order] for c in POS], axis=1)
    q = np.stack([np.asarray(d[c], dtype=float)[order] for c in QUAT], axis=1)
    disp = np.linalg.norm(p - p[0], axis=1)
    rot = angle_deg(q[0], q)
    moved = np.flatnonzero((disp > pos_cm / 100.0) | (rot > rot_deg))
    first = int(moved[0]) if moved.size else -1
    print(f"{path}：{len(p)} 帧；第一次离开（平移 > {pos_cm} cm 或转角 > {rot_deg}°）在第 {first} 帧；"
          f"最终平移 {disp[-1]:.3f} m、转角 {rot[-1]:.1f}°、高度变化 {p[-1, 2] - p[0, 2]:+.3f} m")
    print("  帧\t平移 m\t转角 °\t高度变化 m")
    for f in MARKS:
        if f < len(p):
            print(f"  {f}\t{disp[f]:.3f}\t{rot[f]:.1f}\t{p[f, 2] - p[0, 2]:+.3f}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pos-cm", type=float, default=3.0)
    ap.add_argument("--rot-deg", type=float, default=10.0)
    ap.add_argument("parquet", nargs="+")
    a = ap.parse_args()
    for path in a.parquet:
        one(path, a.pos_cm, a.rot_deg)
    print("OBJECT_ONSET_DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
