"""Checks registered for plan-t3flip13 v2.1 (H0 f, the storm reports, the pure-symmetry boundary check), Tier 3 inputs only.

Plan: agent-doc/plan-t3flip13-2026-10-27.md on track2/p1-training, version 2.1, section 1 step 5 and section 2.

    python t3_flip13_checks.py <tier3 root> <ep> <old dyn7 version> <hr version> <new dyn7 version | -> <physics dir of hr>
Prints, for the episode:
  branch     H0(f): the new dyn7 layer against the old one - frames of the pre-storm part within 2 deg of the old pose, and
             frames of the post-storm part within 5 deg of old @ flip_a2 (the plan names the frame ranges; here they come
             from the held_fix record: before the first storm, after each storm);
  storms     per storm (from the held_fix record): g_best, the angle between the two ends on the chosen branch and on the
             other branch, the slerp axis angle to the floor normal, the world flip_a2 axis angle to the floor normal at
             the storm's two end frames, the centre-of-mass step inside the storm against the episode's p99, the lowest
             hull point inside the storm against the floor;
  boundary   every _hr frame whose turn exceeds 24 deg, with its residual modulo the symmetry group (must be <= 1 deg).
Last line T3_FLIP13_CHECKS_DONE <fails>.
"""
import json
import sys
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE / "gate"), str(HERE.parents[2] / "libs" / "v2d_infra")]


def angle(a, b) -> float:
    return float(np.degrees(np.arccos(np.clip((np.trace(a.T @ b) - 1) / 2, -1, 1))))


def main() -> None:
    import trimesh
    from tier_guard import forbid_lower_tiers
    forbid_lower_tiers()
    import t3_inputs
    from t3_align_check import world_pose
    from t3_fix_units import principal, rot
    from t3_support import basis
    from t3_symmetry import Shape, symmetries

    root, ep, v_old, v_hr, v_new, phys = Path(sys.argv[1]), int(sys.argv[2]), sys.argv[3], sys.argv[4], sys.argv[5], Path(sys.argv[6])
    metas = {m["episode_index"]: m for m in map(json.loads, (root / "input/meta/episodes_metadata.jsonl").read_text().splitlines()) if m}
    m = metas[ep]
    name = f"ep{ep:02d}_{m['object']}"
    rec = next(r for r in json.loads((root / "runs" / f"{v_hr}.held_fix.json").read_text()) if r["episode"] == name)
    mesh = trimesh.load(root / "input" / m["mesh"], force="mesh")
    body = mesh if mesh.is_watertight else mesh.convex_hull
    com_b = np.asarray(body.center_mass)
    G, _ = symmetries(Shape(mesh, com_b), body.moment_inertia)
    moments, axes = principal(body.moment_inertia)
    g2 = rot(axes[:, 2], 180)
    n_up, d_up, _, _, _ = basis(t3_inputs.ground_plane(root, m))
    hull = np.asarray(mesh.convex_hull.vertices, np.float64)
    T_old, T_hr = world_pose(root, v_old, ep), world_pose(root, v_hr, ep)
    R_old, R_hr = T_old[:, :3, :3], T_hr[:, :3, :3]
    n = len(R_old)
    fails = 0
    storms = [tuple(st) for r in rec["runs"] for st in r["storms"]]
    print(f"== {name}：{n} 帧；|G| {len(G)}；风暴 {storms}")
    # storms
    com_hr = T_hr[:, :3, 3] + np.einsum("nij,j->ni", R_hr, com_b)
    step = np.linalg.norm(np.diff(com_hr, axis=0), axis=1)
    p99 = float(np.percentile(step, 99))
    low = (np.einsum("fij,kj->fki", R_hr, hull) + T_hr[:, None, :3, 3]) @ n_up + d_up
    for kind, a, b in storms:
        g_best = min([np.eye(3), *[np.asarray(g) for g in G[1:]]], key=lambda g: angle(R_hr[a], R_old[b] @ g))
        on, other = angle(R_hr[a], R_old[b] @ g_best), max(angle(R_hr[a], R_old[b] @ np.asarray(g)) for g in [np.eye(3), *G[1:]])
        rel = Rotation.from_matrix(R_hr[a].T @ R_hr[b]).as_rotvec()
        ax_w = R_hr[a] @ (rel / max(1e-9, np.linalg.norm(rel)))
        tilt = float(np.degrees(np.arccos(min(1.0, abs(float(ax_w @ n_up))))))
        fa, fb = [float(np.degrees(np.arccos(min(1.0, abs(float((R_hr[t] @ axes[:, 2]) @ n_up)))))) for t in (a, b)]
        sm, lo = float(step[a:b].max()), float(low[a:b].min())
        ok = sm <= 2 * p99 and lo >= -0.01
        fails += int(not ok)
        print(f"风暴 {kind} {a}–{b}（{b - a} 帧，无掩码观测）：两端在选中支上差 {on:.1f}°、另一支 {other:.1f}°；插值轴与地面法线夹角 {tilt:.1f}°；"
              f"flip_a2 轴与地面法线夹角 第 {a} 帧 {fa:.1f}°、第 {b} 帧 {fb:.1f}°（< 30° 记连续性先验弱）；质心步长最大 {sm * 100:.2f} cm（整集 p99 {p99 * 100:.2f}）；最低点 {lo * 100:+.1f} cm {'过' if ok else '不过'}")
    # boundaries in _hr
    td = np.r_[0.0, [angle(R_hr[t - 1], R_hr[t]) for t in range(1, n)]]
    big = [t for t in range(1, n) if td[t] > 24]
    processed = np.zeros(n, bool)
    for r in rec["runs"]:
        processed[r["start"]:r["end"]] = True
    for t in big:
        res = min(angle(R_hr[t - 1] @ np.asarray(g), R_hr[t]) for g in [np.eye(3), *G[1:]])
        if processed[t] and processed[t - 1]:
            fails += 1
            print(f"_hr 第 {t} 帧转角 {td[t]:.1f}°，在处理过的段内 不过")
        elif processed[t] or processed[t - 1]:
            ok = res <= 1.0
            fails += int(not ok)
            print(f"_hr 第 {t} 帧转角 {td[t]:.1f}°（段与歇着段的边界），对称群取模后残差 {res:.2f}° {'过' if ok else '不过'}")
        else:
            print(f"_hr 第 {t} 帧转角 {td[t]:.1f}°，在输入的歇着段里（dyn7 锁定时消掉），取模残差 {res:.2f}° 只报")
    if not big:
        print("_hr 没有 > 24° 的帧")
    # H0(f) on the new dyn7 layer
    if v_new != "-":
        T_new = world_pose(root, v_new, ep)
        R_new = T_new[:, :3, :3]
        first = min(a for _, a, b in storms) if storms else n
        pre = [angle(R_old[t], R_new[t]) for t in range(0, first)]
        print(f"H0(f) 前段 0–{first}：新 dyn7 对旧 dyn7 最大 {max(pre):.1f}°（要 ≤ 2°）{'过' if max(pre) <= 2 else '不过'}")
        fails += int(max(pre) > 2)
        ends = sorted(b for _, a, b in storms)
        for i, b in enumerate(ends):
            e = ends[i + 1] - 30 if i + 1 < len(ends) else n
            seg = range(b + 1, e)
            post = [angle(R_old[t] @ g2, R_new[t]) for t in seg]
            same = [angle(R_old[t], R_new[t]) for t in seg]
            print(f"H0(f) 后段 {b + 1}–{e}：新 dyn7 对旧 dyn7·flip_a2 最大 {max(post):.1f}°（要 ≤ 5°）{'过' if max(post) <= 5 else '不过'}；对旧 dyn7 本身中位 {np.median(same):.1f}°")
            fails += int(max(post) > 5)
    print(f"T3_FLIP13_CHECKS_DONE {fails}")


if __name__ == "__main__":
    main()
