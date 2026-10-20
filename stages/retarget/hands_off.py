"""参考里让机器人不去够物体（训练机上经 scripts/dev/in-flash-chord 在容器里跑，只用 CPU）。
起因：agent-doc/plan-t12lift-2026-10-20.md：Tier 2 ep25 训好的策略把瓶子弄到地上、4096 世界 MPPE 117.09 cm，而物体一直不动时只有 49.51 cm（`results/t2diag/t2_static_floor.txt`）；
Tier 1 ep25 同样（114.10 对 49.71，`results/select_t1/t1_static_floor_c10s43.txt`）。这里给出一份“走路照参考、两条手臂不去够物体”的参考，训出的策略只当保底候选。
做法：两条手臂（shoulder_pitch/roll/yaw、elbow、wrist_roll/pitch/yaw）与 14 个 Dex3 手指关节在全部帧都换成 --arm-frame 那一帧的值（默认第 0 帧：参考开头人还没伸手），
腿、腰、根照抄；ee_pose_w（两只手掌）按 URDF 正向运动学重算（四元数 wxyz，与原 parquet 一致；先自检原关节角下算出的手掌与原 ee_pose_w 最大差 ≤ 2 mm，不过就退出）；
hand_contact_active 全部置 0（没有接触段，force_closure 不计）。其余列、object 目录、支撑面、v2d_meta.json 照抄（同 finger_close.py 的写法）。
报告：手臂关节的最大改动、新参考里两只手掌到物体表面采样点的最近距离的分位（全部帧，判断会不会碰到物体）、原参考的同一数（对照）。
用法（容器内）：python /repo/stages/retarget/hands_off.py <motion parquet> <out_root> --meta-src <motion_src 档位目录> --meta-dst <新档位目录> [--arm-frame 0] [--dry-run]
最后一行 HANDS_OFF_DONE
"""
import argparse
import shutil
import sys
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import trimesh
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
from finger_close import URDF, Robot, quat_mat

ARM = ("shoulder_pitch", "shoulder_roll", "shoulder_yaw", "elbow", "wrist_roll", "wrist_pitch", "wrist_yaw")


def mat_to_wxyz(R: np.ndarray) -> np.ndarray:
    """(N,3,3) → (N,4) wxyz，w ≥ 0。"""
    out = np.empty((R.shape[0], 4))
    for i, m in enumerate(R):
        tr = np.trace(m)
        if tr > 0:
            s = np.sqrt(tr + 1.0) * 2
            out[i] = [0.25 * s, (m[2, 1] - m[1, 2]) / s, (m[0, 2] - m[2, 0]) / s, (m[1, 0] - m[0, 1]) / s]
        elif m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
            s = np.sqrt(1.0 + m[0, 0] - m[1, 1] - m[2, 2]) * 2
            out[i] = [(m[2, 1] - m[1, 2]) / s, 0.25 * s, (m[0, 1] + m[1, 0]) / s, (m[0, 2] + m[2, 0]) / s]
        elif m[1, 1] > m[2, 2]:
            s = np.sqrt(1.0 + m[1, 1] - m[0, 0] - m[2, 2]) * 2
            out[i] = [(m[0, 2] - m[2, 0]) / s, (m[0, 1] + m[1, 0]) / s, 0.25 * s, (m[1, 2] + m[2, 1]) / s]
        else:
            s = np.sqrt(1.0 + m[2, 2] - m[0, 0] - m[1, 1]) * 2
            out[i] = [(m[1, 0] - m[0, 1]) / s, (m[0, 2] + m[2, 0]) / s, (m[1, 2] + m[2, 1]) / s, 0.25 * s]
    out[out[:, 0] < 0] *= -1
    return out / np.linalg.norm(out, axis=1, keepdims=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("motion")
    ap.add_argument("out_root")
    ap.add_argument("--meta-src", required=True)
    ap.add_argument("--meta-dst", required=True)
    ap.add_argument("--arm-frame", type=int, default=0)
    ap.add_argument("--urdf", default=URDF)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    motion = Path(a.motion)
    seq_dir = motion.parents[1]
    seq = seq_dir.name.split("=", 1)[1]
    whole = seq_dir.parents[1]
    out_seq = Path(a.out_root) / "whole_body" / "soma" / seq_dir.name
    meta_src = Path(a.meta_src) / seq / "v2d_meta.json"
    meta_dst = Path(a.meta_dst) / seq / "v2d_meta.json"
    if not a.dry_run and (out_seq.exists() or meta_dst.exists()):
        print(f"{out_seq} 或 {meta_dst} 已存在，拒绝")
        return 2
    if not meta_src.is_file():
        print(f"没有 {meta_src}")
        return 2
    t = pq.read_table(motion)
    row = t.to_pylist()[0]
    names = list(row["robot_joint_names"])
    qj = np.asarray(row["robot_joint_positions"], dtype=float)
    T = qj.shape[0]
    rob = Robot(a.urdf)
    root_p = np.asarray(row["robot_root_position"], dtype=float)
    root_R = quat_mat(np.asarray(row["robot_root_wxyz"], dtype=float), "wxyz")
    ee = np.asarray(row["ee_pose_w"], dtype=float)
    ee_names = list(row["ee_link_names"])
    palms = set(ee_names)
    fk0 = rob.fk(root_p, root_R, {n: qj[:, i] for i, n in enumerate(names)}, palms)
    for k, ln in enumerate(ee_names):
        dp = float(np.linalg.norm(fk0[ln][0] - ee[:, k, :3], axis=1).max())
        R0 = quat_mat(ee[:, k, 3:], "wxyz")
        ang = float(np.degrees(np.arccos(np.clip((np.einsum("nij,nij->n", R0, fk0[ln][1]) - 1) / 2, -1, 1))).max())
        print(f"  自检 {ln}：原关节角下位置最大差 {dp * 1000:.2f} mm、朝向最大差 {ang:.3f}°")
        if dp > 0.002 or ang > 1.0:
            print("FK_SELFCHECK_FAIL，不写文件")
            return 3
    idx = [i for i, n in enumerate(names) if any(n == f"{s}_{j}_joint" for s in ("left", "right") for j in ARM) or "_hand_" in n]
    if len(idx) != 28:
        print(f"手臂与手指关节应为 28 个，找到 {len(idx)} 个：{[names[i] for i in idx]}")
        return 3
    new_q = qj.copy()
    new_q[:, idx] = qj[a.arm_frame, idx][None, :]
    print(f"参考 {motion}：{T} 帧；手臂与手指 28 个关节固定为第 {a.arm_frame} 帧的值；关节最大改动 {np.abs(new_q - qj).max():.3f} rad；"
          f"其余关节改动 {np.abs(np.delete(new_q - qj, idx, axis=1)).max():.3g} rad")
    fk1 = rob.fk(root_p, root_R, {n: new_q[:, i] for i, n in enumerate(names)}, palms)
    new_ee = ee.copy()
    for k, ln in enumerate(ee_names):
        new_ee[:, k, :3] = fk1[ln][0]
        new_ee[:, k, 3:] = mat_to_wxyz(fk1[ln][1])
    # 手掌到物体表面的最近距离（原参考对新参考）
    mesh = trimesh.load(row["object_mesh_paths"][0], force="mesh")
    sp, _ = trimesh.sample.sample_surface(mesh, 20000, seed=0)
    tree = cKDTree(sp)
    op = np.asarray(row["object_body_position"], dtype=float)[:, 0]
    oR = quat_mat(np.asarray(row["object_body_wxyz"], dtype=float)[:, 0], "wxyz")
    for tag, e_ in (("原参考", ee), ("新参考", new_ee)):
        d = np.stack([tree.query((e_[:, k, :3] - op)[:, None, :] @ oR)[0][:, 0] for k in range(len(ee_names))], 1).min(1)
        print(f"  {tag}：两只手掌到物体表面的最近距离 全部帧分位 1/10/50 = {np.percentile(d, 1):.3f} / {np.percentile(d, 10):.3f} / {np.percentile(d, 50):.3f} m，"
              f"最小 {d.min():.3f} m（第 {int(d.argmin())} 帧）")
    if a.dry_run:
        print("dry-run：不写文件")
        print("HANDS_OFF_DONE")
        return 0
    out_seq.mkdir(parents=True)
    shutil.copytree(seq_dir / "object", out_seq / "object")
    (out_seq / "robot_name=g1").mkdir()
    t2 = t
    for col, val in (("robot_joint_positions", [new_q.tolist()]), ("ee_pose_w", [new_ee.tolist()]),
                     ("hand_contact_active", [np.zeros_like(np.asarray(row["hand_contact_active"])).tolist()])):
        f = t2.schema.field(col)
        t2 = t2.set_column(t2.schema.get_field_index(col), f, pa.array(val, type=f.type))
    swapped = 0
    for col in ("object_mesh_paths", "object_urdf_paths"):
        old = t2.column(col).to_pylist()[0]
        vals = [[p.replace(str(seq_dir), str(out_seq)) for p in old]]
        swapped += sum(n != o for n, o in zip(vals[0], old))
        f = t2.schema.field(col)
        t2 = t2.set_column(t2.schema.get_field_index(col), f, pa.array(vals, type=f.type))
    if swapped == 0:
        shutil.rmtree(out_seq)
        print(f"MESH_PATH_FAIL：网格路径没有一条以 {seq_dir} 开头，新目录已撤回")
        return 3
    pq.write_table(t2, out_seq / "robot_name=g1" / "data.parquet")
    st_dst = Path(a.out_root) / "whole_body" / "reconstructed_stage"
    st_dst.mkdir(parents=True, exist_ok=True)
    for f in (whole / "reconstructed_stage").glob(f"{seq}_*"):
        shutil.copy2(f, st_dst / f.name)
    meta_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(meta_src, meta_dst)
    print(f"写出 {out_seq}、{st_dst} 里这一集的支撑面与 {meta_dst}；网格路径换了 {swapped} 条")
    print("HANDS_OFF_DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
