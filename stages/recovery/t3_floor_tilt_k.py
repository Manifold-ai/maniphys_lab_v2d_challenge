"""Tier 3：标定内参能不能消掉重建里的地面倾斜（Mac 上跑，要 numpy、trimesh、scipy；只读 CARI4D 的相机系物体位姿、另一位用户选出的地面静置事件、
官方网格与发布的地面平面，不读任何轨迹真值，不读 Tier 1、Tier 2 轨迹）。计划 agent-doc/plan-t3-kfix-2026-10-16.md 方案 2a 与判据第 1 条。

背景：交付版链路在相机系里看到静置物体的最低点随深度升高（714 个主机位地面事件，倾斜 3.83°），世界步用 R_floor 把它转平
（另一位用户的 t3_floor_fit.py）。按推导，这个倾斜主要来自主点 cy 用错：流程用 576，标定值约 533，(576 − 533)/830 ≈ 3.0°。

做法：事件来自 t3_camera_height.py 的 event_rows（物体静止、不挨着人、渲染与掩码一致、靠近地面），每个事件取 CARI4D 那一帧的位姿
T（相机 ← 官方网格局部系，内参 K_c）。按“像素不变”换到某套内参 K 下：网格原点的像素 p = K_c t；新视线 r = K⁻¹[p, 1]；深度两种口径——
口径一 z 随 f 成比例（z_K = z_c · f_K / f_c），口径二 沿视线的距离取焦距步之后的 ‖t_830‖；朝向随视线转（从 t 的方向到新方向的最小转动，
同 t3_convert_ep.py 的 _ray_turn）。接触点取凸包顶点里沿当前地面法向最低的那个（与 t3_floor_fit.py 相同），每集等权，加权最小二乘拟平面，
Huber（3 cm）重加权 5 轮，法向迭代 3 次。
变体：P = 流程的焦距步（fx 830、主点 (768, 576)，深度乘 830/f_c，同 t3_convert_ep.py focal）——正对照，应复现约 3.8° 的倾斜；
G1、G2 = 方格内参（f 866.3、cx 702.8、cy 535.1，ceiling_grid_main9 拟合 G）的口径一、口径二；B1、B2 = 曼哈顿拟合 B 的内参（860.8、790.0、527.5）。
GB1（方格拟合 GB 的内参，cy 531.1）是看到 G1 的结果之后加的探索，不参与判读。
报：拟出的平面相对发布地面的倾斜（度），并拆成绕相机 x 轴（俯仰，随深度）与绕光轴（横滚，随横向）两个分量、拟出的离地高度与发布 d 之差（cm）、接触点相对发布地面的高度残差（中位、中位绝对偏差，cm）、
接触点高度随深度的斜率（cm/m）。
判读（看结果之前登记于计划）：P 的倾斜在 3.83° ± 0.3° 内记“正对照复现”；G1、G2 的倾斜都 ≤ 1.0° 记“标定内参解释了地面倾斜”，任一 > 1.0° 记
“标定内参解释不了地面倾斜”；口径按 |高度残差中位| 小的取（相差 < 0.5 cm 取口径一）。
用法：uv run --no-project --python 3.12 --with numpy --with scipy --with trimesh python stages/recovery/t3_floor_tilt_k.py
     [--events runs/t3world/floor/camera_height_main.json] [--budget runs/t3world/budget]
最后一行 FLOOR_TILT_K_DONE。
"""
import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

ROOT = Path(__file__).resolve().parents[2]
DS = ROOT / "data/challenge/track_2/tier_2_synthetic_noise"
HUBER_M = 0.03
VARIANTS = {   # 名字：(f, cx, cy, 口径)；口径 None 表示流程的焦距步
    "P 流程焦距步（830、768、576）": (830.0, 768.0, 576.0, None),
    "G1 方格（口径一）": (866.3, 702.8, 535.1, 1),
    "G2 方格（口径二）": (866.3, 702.8, 535.1, 2),
    "B1 曼哈顿 B（口径一）": (860.8, 790.0, 527.5, 1),
    "B2 曼哈顿 B（口径二）": (860.8, 790.0, 527.5, 2),
    "GB1 方格 GB（口径一，事后加的探索）": (866.3, 701.8, 531.1, 1),
}


def unit(v: np.ndarray) -> np.ndarray:
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


def ray_turn(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """从方向 a 到方向 b 的最小转动（单个）。"""
    a, b = unit(a), unit(b)
    ax = np.cross(a, b)
    s = np.linalg.norm(ax)
    ang = math.atan2(s, float(a @ b))
    return Rotation.from_rotvec(ax / s * ang if s > 1e-12 else np.zeros(3)).as_matrix()


def released_plane() -> tuple:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import t3_manhattan_calib as mc
    n = mc.floor_normal()
    ds = []
    for line in (DS / "meta/episodes_metadata.jsonl").read_text().splitlines():
        m = json.loads(line)
        if int(m["episode_index"]) in mc.SECOND | mc.SIDE:
            continue
        p = np.array(json.loads((DS / m["ground_plane"]).read_text())["plane"], float)
        k = np.linalg.norm(p[:3])
        ds.append(abs(p[3] / k))
    return n, float(np.median(ds))


def reexpress(T: np.ndarray, kc: np.ndarray, var: tuple) -> tuple:
    f, cx, cy, mode = var
    t, R = T[:3, 3], T[:3, :3]
    fc = float(kc[0, 0])
    if mode is None:   # 流程的焦距步：主点不动，深度乘 f/fc
        t2 = t * np.array([1.0, 1.0, f / fc])
    else:
        p = kc @ t
        r = np.linalg.inv(np.array([[f, 0, cx], [0, f, cy], [0, 0, 1.0]])) @ np.array([p[0] / p[2], p[1] / p[2], 1.0])
        if mode == 1:
            t2 = r * (t[2] * f / fc) / r[2]
        else:
            t830 = t * np.array([1.0, 1.0, 830.0 / fc])
            t2 = unit(r) * np.linalg.norm(t830)
    return ray_turn(t, t2) @ R, t2


def fit_plane(p: np.ndarray, w: np.ndarray, up: np.ndarray) -> tuple:
    ww = w.copy()
    for _ in range(5):
        c = (p * ww[:, None]).sum(0) / ww.sum()
        C = ((p - c) * ww[:, None]).T @ (p - c)
        n = np.linalg.eigh(C)[1][:, 0]
        n = n if n @ up > 0 else -n
        d = -float(n @ c)
        r = np.abs(p @ n + d)
        ww = w * np.minimum(1.0, HUBER_M / np.maximum(r, 1e-9))
    return n, d


def main() -> int:
    import trimesh
    ap = argparse.ArgumentParser()
    ap.add_argument("--events", type=Path, default=ROOT / "runs/t3world/floor/camera_height_main.json")
    ap.add_argument("--budget", type=Path, default=ROOT / "runs/t3world/budget")
    a = ap.parse_args()
    sys.path.insert(0, str(ROOT / "libs/v2d_infra"))
    from tier_guard import forbid_tier1
    forbid_tier1()
    n_rel, d_rel = released_plane()
    rows = json.loads(a.events.read_text())["event_rows"]
    meta = {f"ep{int(m['episode_index']):02d}_{m['object']}": m for m in
            map(json.loads, (DS / "meta/episodes_metadata.jsonl").read_text().splitlines())}
    eps = sorted({r["episode"] for r in rows})
    data = {}
    for ep in eps:
        oc = np.load(a.budget / ep / "object_cam.npz")
        hull = np.asarray(trimesh.load(DS / meta[ep]["mesh"], force="mesh").convex_hull.vertices, np.float64)
        data[ep] = (oc["T_cam_glb"].astype(np.float64), oc["intrinsics"].astype(np.float64), hull)
    print(f"== {len(rows)} 个地面事件，{len(eps)} 集；发布地面 n = ({n_rel[0]:+.5f}, {n_rel[1]:+.5f}, {n_rel[2]:+.5f})，d {d_rel:.4f} m")
    for name, var in VARIANTS.items():
        pts, w, epi = [], [], []
        poses = {}
        for r in rows:
            T, kc, hull = data[r["episode"]]
            poses.setdefault(r["episode"], []).append(reexpress(T[r["frame"]], kc, var))
        up = n_rel.copy()
        for _ in range(3):   # 接触点取沿当前法向最低的凸包顶点，法向迭代
            pts, w, epi = [], [], []
            for ep, plist in poses.items():
                hull = data[ep][2]
                for R, t in plist:
                    X = hull @ R.T + t
                    pts.append(X[np.argmin(X @ up)])
                    w.append(1.0 / len(plist))
                    epi.append(ep)
            pts, w = np.array(pts), np.array(w)
            up, d = fit_plane(pts, w, n_rel)
        tilt = math.degrees(math.acos(min(1.0, float(up @ n_rel))))
        # 分量：把 up 与 n_rel 投到相机 y-z 平面（俯仰）与 x-y 平面（横滚）里比角度
        pitch = math.degrees(math.atan2(up[2], -up[1]) - math.atan2(n_rel[2], -n_rel[1]))
        roll = math.degrees(math.atan2(up[0], -up[1]) - math.atan2(n_rel[0], -n_rel[1]))
        h = pts @ n_rel + d_rel   # 接触点相对发布地面的高度（正 = 在地面上方）
        depth = pts[:, 2]
        slope = np.polyfit(depth, h, 1, w=w)[0]
        med = float(np.median(h))
        mad = float(np.median(np.abs(h - med)))
        print(f"  {name}：拟出的平面相对发布地面倾斜 {tilt:.2f}°（俯仰分量 {pitch:+.2f}°、横滚分量 {roll:+.2f}°），离地高度 {d:.4f} m（发布 d − 拟出 {100 * (d_rel - d):+.1f} cm）；"
              f"接触点相对发布地面的高度中位 {100 * med:+.1f} cm、中位绝对偏差 {100 * mad:.1f} cm，随深度的斜率 {100 * slope:+.2f} cm/m")
    print("FLOOR_TILT_K_DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
