"""训好的策略的残差有多少时候贴着上限（训练机上经 scripts/dev/in-flash-chord 在容器里跑，只用 CPU；读 diag_rollout.py --actions --bodies 存的 npz；只报不判）。
计划 agent-doc/plan-trajopt-2026-10-26.md 第 5 节（C 段）。policy_action (N,W',A) 是 actor 的确定性输出 action_scale·tanh(均值)，还没乘 residual_scale；
|残差| ≥ --sat（默认 9.5，即 tanh ≥ 0.95，action_scale 10）记“贴上限”。动作的顺序 = 配置里 residual_joint_names 的顺序，后接 14 个手指（--names 给那份 yaml）。
关节分组：腿（hip、knee、ankle）、腰（waist）、手臂（shoulder、elbow、wrist）、手指（其余 14 个）。
摔倒帧照 stages/evaluate/fall_mechanism.py：躯干倾斜误差（仿真躯干 z 轴与参考躯干 z 轴的夹角，参考躯干用 URDF 正向运动学）第一次 > --fall-rad（默认 0.6）。
窗口：摔了的世界取摔倒前 --pre（默认 30）帧；没摔的世界取第一次接触后 --post（默认 150）帧（接触帧取参考 hand_contact_active 任一侧的第一帧）；另报全程（前 N 帧）。
用法（容器内）：python /repo/stages/evaluate/residual_saturation.py --npz <npz> --motion <parquet> --names <sonic_joint_residual.yaml> [--label 名]   最后一行 RESIDUAL_SATURATION_DONE
"""
import argparse
import re
import sys
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "stages" / "retarget"))
from finger_close import URDF, Robot, quat_mat  # noqa: E402

GROUPS = {"腿": ("hip", "knee", "ankle"), "腰": ("waist",), "手臂": ("shoulder", "elbow", "wrist")}


def residual_names(yaml_path: str) -> list:
    names, on = [], False
    for line in Path(yaml_path).read_text().splitlines():
        if line.startswith("residual_joint_names:"):
            on = True
            continue
        if on:
            m = re.match(r"\s+-\s+(\S+)", line)
            if not m:
                break
            names.append(m.group(1))
    return names


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--npz", required=True)
    ap.add_argument("--motion", required=True)
    ap.add_argument("--names", required=True)
    ap.add_argument("--label", default="")
    ap.add_argument("--sat", type=float, default=9.5)
    ap.add_argument("--fall-rad", type=float, default=0.6)
    ap.add_argument("--pre", type=int, default=30)
    ap.add_argument("--post", type=int, default=150)
    a = ap.parse_args()
    z = np.load(a.npz, allow_pickle=False)
    act = np.asarray(z["policy_action"], dtype=np.float64)                    # (N, W', A)
    aw = np.asarray(z["policy_action_worlds"], dtype=np.int64)
    body = np.asarray(z["robot_body_pose"], dtype=np.float64)                  # (T, W, 4, 7)
    names = [str(x) for x in z["robot_body_names"]] if "robot_body_names" in z.files else []
    s0 = int(z["start_frame"])
    N, Wp, A = act.shape
    rn = residual_names(a.names)
    if A != len(rn) + 14:
        print(f"动作维数 {A} ≠ 残差关节 {len(rn)} + 14 个手指，退出")
        return 3
    groups = {g: [i for i, n in enumerate(rn) if any(k in n for k in keys)] for g, keys in GROUPS.items()}
    groups["手指"] = list(range(len(rn), A))
    row = pq.read_table(a.motion).to_pylist()[0]
    jn = list(row["robot_joint_names"])
    qj = np.asarray(row["robot_joint_positions"], dtype=float)
    rp = np.asarray(row["robot_root_position"], dtype=float)
    rR = quat_mat(np.asarray(row["robot_root_wxyz"], dtype=float), "wxyz")
    rob = Robot(URDF)
    T = min(N, body.shape[0])
    frames = np.arange(s0, s0 + T).clip(0, len(qj) - 1)
    ref = rob.fk(rp[frames], rR[frames], {n: qj[frames, i] for i, n in enumerate(jn)}, {"torso_link"})["torso_link"][1]   # (T,3,3)
    ti = names.index("torso_link") if names else 1
    simR = quat_mat(body[:T, aw, ti, 3:].reshape(-1, 4), "xyzw").reshape(T, len(aw), 3, 3)
    cosang = np.einsum("twi,ti->tw", simR[..., :, 2], ref[:, :, 2]).clip(-1, 1)
    tilt = np.arccos(cosang)                                                  # (T, W')
    over = tilt > a.fall_rad
    fall = np.where(over.any(0), over.argmax(0), -1)
    c = np.asarray(row["hand_contact_active"], dtype=bool)
    tc = min((int(np.flatnonzero(x)[0]) for x in c if x.any()), default=len(qj)) - s0
    sat = np.abs(act[:T]) >= a.sat                                            # (T, W', A)
    win = np.zeros((T, len(aw)), bool)
    for w in range(len(aw)):
        if fall[w] >= 0:
            win[max(0, fall[w] - a.pre):fall[w], w] = True
        else:
            win[max(0, tc):min(T, tc + a.post), w] = True
    fell = int((fall >= 0).sum())
    print(f"{a.label}：{T} 帧、{len(aw)} 个世界；摔了的世界 {fell}（摔倒帧中位 {int(np.median(fall[fall >= 0])) if fell else '—'}）；参考第一次接触 第 {tc + s0} 帧")
    print("组\t关节数\t窗口里贴上限比例\t全程贴上限比例\t窗口里 |残差| 均值")
    for g, idx in groups.items():
        if not idx:
            continue
        s = sat[:, :, idx]
        wn = win[:, :, None].repeat(len(idx), 2)
        print(f"{g}\t{len(idx)}\t{s[wn].mean():.3f}\t{s.mean():.3f}\t{np.abs(act[:T][:, :, idx])[wn].mean():.2f}")
    print("RESIDUAL_SATURATION_DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
