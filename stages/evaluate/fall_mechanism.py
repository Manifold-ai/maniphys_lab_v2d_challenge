"""机器人怎么摔的：摔之前哪一项先坏（训练机上经 scripts/dev/in-flash-chord 在容器里跑，只用 CPU；读 diag_rollout.py --bodies 存的 npz；只报不判）。
计划 agent-doc/plan-t12fall-2026-10-20.md（判据写在计划里）。输入：npz（robot_body_pose (T,W,4,7)：pelvis、torso_link、left/right_ankle_roll_link 的位置 + 四元数 xyzw；
achieved_pose_w 等同 diag_rollout）与同一集的参考 parquet（参考的同四个刚体用 URDF 正向运动学算，stages/retarget/finger_close.py 的 Robot）。
逐世界逐帧：躯干倾角（躯干 z 轴与世界 z 轴的夹角）、骨盆高度、骨盆与参考骨盆的水平距离、两只脚与参考同侧脚的水平距离（取较大者）、两只脚离地高度（取较低者）。
“摔倒帧” t_f = 躯干倾角第一次 > --fall-rad（默认 0.6 rad）的帧；没有就记不摔。对摔了的世界，报各项第一次越过门槛的帧相对 t_f 的分布：
  脚踩偏（脚与参考的水平距离 > --foot-m，默认 0.15 m）、骨盆偏（> --pelvis-m，默认 0.15 m）、躯干先歪（倾角 > --tilt-rad，默认 0.3 rad）、双脚离地（较低的脚离地 > 0.05 m，持续 ≥ 3 帧）。
另报全部世界在 --marks 帧上各项的世界中位，供与成功集对比。
用法（容器内）：python /repo/stages/evaluate/fall_mechanism.py --npz <npz> --motion <parquet> [--label 名] [--marks 0 50 100 ...]   最后一行 FALL_MECHANISM_DONE
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "stages" / "retarget"))
from finger_close import URDF, Robot, quat_mat

NAMES = ("pelvis", "torso_link", "left_ankle_roll_link", "right_ankle_roll_link")


def first_over(x: np.ndarray, thr: float, run: int = 1) -> np.ndarray:
    """x (T,W) → 每个世界第一次连续 run 帧 > thr 的起始帧，没有为 -1。"""
    over = x > thr
    if run > 1:
        k = np.ones(run, dtype=int)
        over = np.apply_along_axis(lambda c: np.convolve(c.astype(int), k, mode="full")[run - 1:] >= run, 0, over)
    return np.where(over.any(0), over.argmax(0), -1)


def q5(x: np.ndarray) -> str:
    return " / ".join(f"{np.percentile(x, p):.0f}" for p in (10, 25, 50, 75, 90)) if x.size else "（无）"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--npz", required=True)
    ap.add_argument("--motion", required=True)
    ap.add_argument("--label", default="")
    ap.add_argument("--fall-rad", type=float, default=0.6)
    ap.add_argument("--foot-m", type=float, default=0.15)
    ap.add_argument("--pelvis-m", type=float, default=0.15)
    ap.add_argument("--tilt-rad", type=float, default=0.3)
    ap.add_argument("--marks", type=int, nargs="*", default=[0, 25, 50, 75, 100, 125, 150, 200, 300])
    ap.add_argument("--urdf", default=URDF)
    a = ap.parse_args()
    z = np.load(a.npz)
    if "robot_body_pose" not in z.files:
        print("npz 里没有 robot_body_pose（要 diag_rollout.py --bodies）")
        return 2
    names = [str(n) for n in z["robot_body_names"]]
    if tuple(names) != NAMES:
        print(f"刚体名 {names} 与期望 {NAMES} 不同")
        return 2
    bp = z["robot_body_pose"].astype(float)                     # (T,W,4,7)
    T, W = bp.shape[:2]
    row = pq.read_table(a.motion, columns=["robot_joint_names", "robot_joint_positions", "robot_root_position", "robot_root_wxyz"]).to_pylist()[0]
    jn = list(row["robot_joint_names"])
    qj = np.asarray(row["robot_joint_positions"], dtype=float)
    s0 = int(z["start_frame"]) if "start_frame" in z.files else 0
    rob = Robot(a.urdf)
    L = rob.fk(np.asarray(row["robot_root_position"], dtype=float), quat_mat(np.asarray(row["robot_root_wxyz"], dtype=float), "wxyz"),
               {n: qj[:, i] for i, n in enumerate(jn)}, set(NAMES))
    ref = {n: L[n][0][s0:s0 + T] for n in NAMES}                # (T,3)
    pos = {n: bp[:, :, k, :3] for k, n in enumerate(NAMES)}
    Rt = quat_mat(bp[:, :, 1, 3:], "xyzw")                       # 躯干 (T,W,3,3)
    tilt = np.arccos(np.clip(Rt[..., 2, 2], -1, 1))             # 躯干 z 轴与世界 z 轴的夹角
    pel_h = pos["pelvis"][..., 2]
    pel_d = np.linalg.norm(pos["pelvis"][..., :2] - ref["pelvis"][:, None, :2], axis=-1)
    foot_d = np.maximum(*(np.linalg.norm(pos[f"{s}_ankle_roll_link"][..., :2] - ref[f"{s}_ankle_roll_link"][:, None, :2], axis=-1) for s in ("left", "right")))
    floor = min(ref["left_ankle_roll_link"][:, 2].min(), ref["right_ankle_roll_link"][:, 2].min())
    foot_lift = np.minimum(pos["left_ankle_roll_link"][..., 2], pos["right_ankle_roll_link"][..., 2]) - floor
    t_f = first_over(tilt, a.fall_rad)
    fell = t_f >= 0
    print(f"{a.label} {a.npz}：{T} 帧、{W} 个世界；摔倒（躯干倾角 > {a.fall_rad} rad）的世界 {int(fell.sum())}（{fell.mean():.1%}），摔倒帧分位 10/25/50/75/90 {q5(t_f[fell].astype(float))}")
    if fell.any():
        for tag, x, thr, run in (("脚踩偏", foot_d, a.foot_m, 1), ("骨盆偏", pel_d, a.pelvis_m, 1), ("躯干先歪", tilt, a.tilt_rad, 1), ("双脚离地", foot_lift, 0.05, 3)):
            f = first_over(x, thr, run)[fell]
            have = f >= 0
            rel = (f[have] - t_f[fell][have]).astype(float)
            print(f"  {tag}（> {thr}）：摔了的世界里出现过 {int(have.sum())}/{int(fell.sum())}；相对摔倒帧 分位 10/25/50/75/90 {q5(rel)}；早于摔倒 ≥ 10 帧的 {int((rel <= -10).sum())}")
    print("  帧\t躯干倾角 rad\t骨盆高 m（参考）\t骨盆偏 m\t脚踩偏 m\t较低的脚离地 m（各项为世界中位）")
    for t in [m for m in a.marks if m < T]:
        print(f"  {t}\t{np.median(tilt[t]):.3f}\t{np.median(pel_h[t]):.3f}（{ref['pelvis'][t, 2]:.3f}）\t{np.median(pel_d[t]):.3f}\t{np.median(foot_d[t]):.3f}\t{np.median(foot_lift[t]):.3f}")
    print("FALL_MECHANISM_DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
