"""Tier 3 误差预算之一：内参这一项让现有交付版重建在世界坐标系里偏了多少（Mac 上跑，要 numpy、pyarrow；只读交付版的物体位姿与
世界步参数，不读 Tier 1，不读 Tier 2，不与任何真值比）。

交付版 tier3_cari4d_f830_best_dr2s_dyn7 的主机位链路（t3_convert_ep.py，另一位用户的分支 track2/tier3-recon）：CARI4D 用
K_c = (fx 835 上下, 主点 (768, 576) 居中) 重建；焦距步骤把 fx 换成 830、深度乘 830/fx_c、主点不动；世界步把相机系绕原点转 R
（地面法向对到发布的 n）再乘 s（离地高度对到发布值），即 X_w = s·R·X_830。所以每帧物体中心可以倒推回像素与深度：
X_830 = Rᵀ X_w / s，p = K_830 X_830，Z = X_830 的 z。

世界坐标系就是主机位相机的坐标系（results/t3world/manhattan_calib_main9_boot.txt，判读“支持”）。真内参 K_t 下，同一个像素 p 的视线是
K_t⁻¹[p, 1]，深度按两种口径给上下界（看结果之前定）：
  口径一（视大小）：深度来自已知网格的视大小，随焦距成比例：X_t = (Z·f_t/830)·K_t⁻¹[p, 1]。
  口径二（距离不变）：沿视线的距离不变，只改方向：X_t = ‖X_830‖·单位(K_t⁻¹[p, 1])。
差 ‖X_t − X_w‖ 是“只把内参改对、别的都不动”时这份重建要移动的量。K_t 列三套：吊顶方格拟合 G、曼哈顿拟合 B、曼哈顿拟合 A
（数值见下 CANDIDATES 与出处）；cx 还没定（agent-doc/experiments/2026-10-16-t3-world-frame.md“没解决”一节），所以三套都报。
另报只看方向的角度误差：流程的世界系视线 R·K_830⁻¹[p, 1] 与 K_t⁻¹[p, 1] 的夹角。

理论预期（看结果之前写下）：方格 K 下偏航约 (768 − 702)/866 ≈ 4.4°，即每米距离横向约 7.7 cm；口径一的深度多 866/830 − 1 ≈ 4.3%；
俯仰：流程转了约 3.7°，真主点比 576 高 (576 − 533)/866 ≈ 2.8°，剩约 0.9° 的俯仰差。
只算主机位 24 集（第二机位 ep12、14、16、25、28 与侧机位 ep21 还叠着配准，另算）。
用法：uv run --no-project --python 3.12 --with numpy --with pyarrow python stages/recovery/t3_k_budget.py [--root runs/t3world/budget]
最后一行 K_BUDGET_DONE。
"""
import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
CANDIDATES = {   # (f, cx, cy)
    "方格 G（ceiling_grid_main3）": (866.2, 702.0, 533.3),
    "曼哈顿 B（manhattan_calib_main9）": (860.8, 790.0, 527.5),
    "曼哈顿 A（manhattan_calib_main9）": (862.2, 847.1, 530.5),
}


def K(f, cx, cy) -> np.ndarray:
    return np.array([[f, 0.0, cx], [0.0, f, cy], [0.0, 0.0, 1.0]])


def unit(v: np.ndarray) -> np.ndarray:
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


def episode(d: Path) -> dict:
    wc = json.loads((d / "world_calib.json").read_text())
    if wc.get("camera_register") or wc.get("camera_group") != 0:
        raise SystemExit(f"{d.name}：不是主机位（camera_group {wc.get('camera_group')}）或带了配准")
    oc = np.load(d / "object_cam.npz")
    kc = oc["intrinsics"]
    f830 = float(wc["focal"]["fx_new"])
    k830 = K(f830, float(kc[0, 2]), float(kc[1, 2]))
    R, s = np.array(wc["rotation"], float), float(wc["scale"])
    pq_file = next(d.glob("episode_*.parquet"))
    t = pq.read_table(pq_file, columns=["observation.object.pose", "observation.object.visible"])
    pose = np.stack(t.column("observation.object.pose").to_numpy(zero_copy_only=False)).astype(float)
    vis = np.asarray(t.column("observation.object.visible").to_numpy(zero_copy_only=False), bool)
    Xw = pose[vis, :3]
    X830 = Xw @ R / s          # Rᵀ X_w / s，按行
    p = X830 @ k830.T
    p = p[:, :2] / p[:, 2:3]
    return {"name": d.name, "Xw": Xw, "X830": X830, "p": p, "f830": f830, "k830": k830, "R": R, "s": s,
            "cxcy": (float(kc[0, 2]), float(kc[1, 2])), "frames": int(vis.sum())}


def budget(ep: dict, kt: tuple) -> dict:
    f, cx, cy = kt
    r = np.c_[ep["p"], np.ones(len(ep["p"]))] @ np.linalg.inv(K(f, cx, cy)).T
    Z = ep["X830"][:, 2]
    x1 = r * (Z * f / ep["f830"])[:, None]                                  # 口径一：视大小
    x2 = unit(r) * np.linalg.norm(ep["X830"], axis=1)[:, None]               # 口径二：距离不变
    ray_pipe = unit(np.c_[ep["p"], np.ones(len(ep["p"]))] @ np.linalg.inv(ep["k830"]).T @ ep["R"].T)
    ang = np.degrees(np.arccos(np.clip((ray_pipe * unit(r)).sum(1), -1, 1)))
    d1, d2 = np.linalg.norm(x1 - ep["Xw"], axis=1), np.linalg.norm(x2 - ep["Xw"], axis=1)
    rng = np.linalg.norm(ep["Xw"], axis=1)
    return {"ang": float(np.median(ang)), "d1": float(np.median(d1)), "d2": float(np.median(d2)), "range": float(np.median(rng)),
            "d1_all": d1, "d2_all": d2}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=ROOT / "runs/t3world/budget")
    a = ap.parse_args()
    eps = [episode(d) for d in sorted(a.root.iterdir()) if d.is_dir()]
    print(f"== 主机位 {len(eps)} 集（{a.root}）；流程内参：fx {eps[0]['f830']:.0f}、主点 {eps[0]['cxcy']}；世界步缩放 "
          f"{min(e['s'] for e in eps):.4f}–{max(e['s'] for e in eps):.4f}")
    for tag, kt in CANDIDATES.items():
        print(f"== 真内参取 {tag}：f {kt[0]}、cx {kt[1]}、cy {kt[2]}")
        print("集\t可见帧\t距离中位(m)\t视线夹角中位(°)\t位移中位 口径一(cm)\t位移中位 口径二(cm)")
        all1, all2 = [], []
        for ep in eps:
            b = budget(ep, kt)
            all1.append(b["d1_all"])
            all2.append(b["d2_all"])
            print(f"{ep['name']}\t{ep['frames']}\t{b['range']:.2f}\t{b['ang']:.2f}\t{100 * b['d1']:.1f}\t{100 * b['d2']:.1f}")
        a1, a2 = np.concatenate(all1), np.concatenate(all2)
        print(f"  全部帧：口径一位移中位 {100 * np.median(a1):.1f} cm、90% 分位 {100 * np.percentile(a1, 90):.1f} cm；"
              f"口径二位移中位 {100 * np.median(a2):.1f} cm、90% 分位 {100 * np.percentile(a2, 90):.1f} cm；"
              f"位移 < 9 cm（AUC 最宽的阈值）的帧占 口径一 {100 * np.mean(a1 < 0.09):.0f}%、口径二 {100 * np.mean(a2 < 0.09):.0f}%")
    print("K_BUDGET_DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
