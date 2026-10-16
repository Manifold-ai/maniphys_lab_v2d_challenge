"""k-fix 的重新表达与另一位用户 convert_kgb（同一组标定内参）逐帧比（ml40 的 v2d_cari4d 镜像里跑，只用 CPU；只读两边的 focal 输出，
不读任何真值，不读 Tier 1、Tier 2）。两份实现同一个映射 M = (f_new/f_used)·K_new⁻¹K_used（深度随焦距）、朝向随视线转、人体骨盆按同一映射、
其余关节刚体跟随；来源是同一个 runs/convert（k-fix 判据 0 核过）。一致到浮点精度就互相印证。
逐集报：物体位置最大差（m）、朝向最大差（度）、两边写的新内参是否相同；人体 transl 与 poses 的最大差。
用法（容器内）：python /k/t3_kfix_vs_kgb.py <k-fix 的 convert 目录> <另一位用户的 convert_kgb 目录>；最后一行 KFIX_VS_KGB_DONE <最大位置差> <最大朝向差>。
"""
import sys
from pathlib import Path

import numpy as np


def angle_max(Ra: np.ndarray, Rb: np.ndarray) -> float:
    tr = np.einsum("nij,nij->n", Ra, Rb)
    return float(np.degrees(np.arccos(np.clip((tr - 1) / 2, -1, 1))).max())


def main() -> int:
    ours, theirs = Path(sys.argv[1]), Path(sys.argv[2])
    worst_t, worst_r, n = 0.0, 0.0, 0
    for d in sorted(ours.glob("ep*")):
        a, b = d / "object_cam_focal.npz", theirs / d.name / "object_cam_focal.npz"
        if not (a.exists() and b.exists()):
            continue
        oa, ob = np.load(a), np.load(b)
        Ta, Tb = oa["T_cam_glb"].astype(np.float64), ob["T_cam_glb"].astype(np.float64)
        if Ta.shape != Tb.shape:
            print(f"{d.name}：帧数不同 {Ta.shape} {Tb.shape}")
            continue
        dt = float(np.abs(Ta[:, :3, 3] - Tb[:, :3, 3]).max())
        dr = angle_max(Ta[:, :3, :3], Tb[:, :3, :3])
        dk = float(np.abs(np.asarray(oa["intrinsics"], float) - np.asarray(ob["intrinsics"], float)).max())
        sa, sb = d / "soma_params_focal.npz", theirs / d.name / "soma_params_focal.npz"
        hum = "人体：缺文件"
        if sa.exists() and sb.exists():
            # allow_pickle：两边的 npz 都是本仓 t3_kfix.py 与另一位用户 t3_convert_ep.py 在同一台服务器上写的（含字符串数组）
            pa, pb = np.load(sa, allow_pickle=True), np.load(sb, allow_pickle=True)
            hum = "人体 " + "、".join(f"{k} 最大差 {float(np.abs(np.asarray(pa[k], float) - np.asarray(pb[k], float)).max()):.2e}"
                                      for k in ("transl", "poses") if k in pa.files and k in pb.files)
        print(f"{d.name}：{len(Ta)} 帧，物体位置最大差 {dt:.2e} m、朝向最大差 {dr:.2e}°，新内参差 {dk:.2e}；{hum}")
        worst_t, worst_r, n = max(worst_t, dt), max(worst_r, dr), n + 1
    print(f"{n} 集；物体位置最大差 {worst_t:.2e} m，朝向最大差 {worst_r:.2e}°")
    print(f"KFIX_VS_KGB_DONE {worst_t:.2e} {worst_r:.2e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
