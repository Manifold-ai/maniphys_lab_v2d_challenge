"""Rebuild CoCoNet's object initialization from FoundationPose's own reliable frames (pilot; runs in the v2d_cari4d image).

Why: the orientation jumps in best_hm are CoCoNet's (stage 06), and CoCoNet starts from FoundationPose's world poses
(`obj_pose_world` of the stage-05 pkl, run_mhr_wild_inference.py). On ep02/03/13/28, 80 of FoundationPose's 86 jump
frames reappear in CoCoNet, and the CoCoNet jumps touch a frame FoundationPose itself marks unreliable 98% of the time on
ep13 (9% of its frames) and 85% on ep28 (33%). `fp_reliable` (run_foundationpose_mhr_export.py) is True when the
first-pass candidate lies within 15 deg (+2.5 deg per frame since the object was last visible) and the adaptive
translation step of the last confirmed pose, or when a reacquisition is confirmed over several frames; it is False on
the relaxed retry path (the last attempt accepts any candidate), on carried frames (the last confirmed pose copied
forward) and when the object was not visible recently (silhouette rank alone). It says "consistent with the previous
confirmed pose", not "right": a wrong branch that FoundationPose keeps stays reliable (ep03 frame 117 is reliable and
56 deg off the video-checked pose).

What it does, per run of unreliable frames no longer than MAX_GAP: the rotation is slerped between the reliable frames
on both sides (held from the one side at the start or end of the episode), about the centre of the mesh bounds so the
object's centre stays where FoundationPose put it; longer runs are left as they are. fp_poses_cam is rewritten from the
new world pose with each frame's camera. The pkl keeps its keys (the stage-06 loader validates them); what was replaced
goes to fp_init.json next to it. The stage-05 marker's output identity is updated so the runner reuses stage 05 and
reruns 06 onward (its signature includes the pkl's identity).

    python t3_fp_init.py <cari4d episode dir> [--max-gap 60]
"""

import json
import os
import pickle
import sys
from pathlib import Path

import numpy as np
import trimesh

MAX_GAP = 60


def quat(R):
    """Rotation matrices (n,3,3) to unit quaternions wxyz (n,4)."""
    q = np.empty((len(R), 4))
    for i, m in enumerate(R):
        t = np.trace(m)
        if t > 0:
            s = np.sqrt(t + 1) * 2
            q[i] = [s / 4, (m[2, 1] - m[1, 2]) / s, (m[0, 2] - m[2, 0]) / s, (m[1, 0] - m[0, 1]) / s]
        else:
            k = int(np.argmax(np.diag(m)))
            a, b = (k + 1) % 3, (k + 2) % 3
            s = np.sqrt(1 + m[k, k] - m[a, a] - m[b, b]) * 2
            q[i, 0] = (m[b, a] - m[a, b]) / s
            q[i, 1 + k] = s / 4
            q[i, 1 + a] = (m[a, k] + m[k, a]) / s
            q[i, 1 + b] = (m[b, k] + m[k, b]) / s
    return q / np.linalg.norm(q, axis=1, keepdims=True)


def rotm(q):
    w, x, y, z = q.T
    return np.stack([np.stack([1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)], -1),
                     np.stack([2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)], -1),
                     np.stack([2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)], -1)], -2)


def slerp(q0, q1, u):
    if np.dot(q0, q1) < 0:
        q1 = -q1
    d = np.clip(np.dot(q0, q1), -1, 1)
    th = np.arccos(d)
    if th < 1e-6:
        return np.repeat(q0[None], len(u), 0)
    return (np.sin((1 - u)[:, None] * th) * q0 + np.sin(u[:, None] * th) * q1) / np.sin(th)


def main():
    args = sys.argv[1:]
    max_gap = int(args[args.index("--max-gap") + 1]) if "--max-gap" in args else MAX_GAP
    c = Path(args[0])
    pkls = sorted((c / "foundationpose").glob("episode_*.pkl"))
    assert len(pkls) == 1, f"expected one episode pkl under {c}/foundationpose, found {len(pkls)}"
    pkl = pkls[0]
    seq = pkl.stem  # the dir may be mounted under another name
    d = pickle.load(open(pkl, "rb"))
    W = np.asarray(d["obj_pose_world"], np.float64)
    C = np.asarray(d["fp_poses_cam"], np.float64)[:, 0]
    rel = np.asarray(d["fp_reliable"], bool) & np.isfinite(W).all((1, 2))
    n = len(W)
    mesh = trimesh.load(c / "export" / seq / "object_mesh" / "output_aligned.glb", force="mesh")
    centre = mesh.bounds.mean(0)
    c2w = W @ np.linalg.inv(C)

    x = np.r_[0, (~rel).astype(int), 0]
    starts, ends = np.flatnonzero(np.diff(x) == 1), np.flatnonzero(np.diff(x) == -1)
    q = quat(W[:, :3, :3])
    newR = W[:, :3, :3].copy()
    replaced, kept = [], []
    for a, b in zip(starts, ends):
        if b - a > max_gap or (a == 0 and b == n):
            kept.append([int(a), int(b)])
            continue
        if a == 0:
            qs = np.repeat(q[b][None], b - a, 0)
        elif b == n:
            qs = np.repeat(q[a - 1][None], b - a, 0)
        else:
            qs = slerp(q[a - 1], q[b], np.arange(1, b - a + 1) / (b - a + 1))
        newR[a:b] = rotm(qs)
        replaced.append([int(a), int(b)])
    turn = np.degrees(np.arccos(np.clip((np.einsum("tij,tij->t", newR, W[:, :3, :3]) - 1) / 2, -1, 1)))
    newW = W.copy()
    newW[:, :3, :3] = newR
    newW[:, :3, 3] = W[:, :3, :3] @ centre + W[:, :3, 3] - newR @ centre
    changed = (newR != W[:, :3, :3]).any((1, 2))  # exact: arccos of a float32 rotation's trace is never 0
    untouched = np.ones(n, bool)
    for a, b in replaced:
        untouched[a:b] = False
    assert not changed[untouched].any(), "a frame outside the replaced runs changed"
    d["obj_pose_world"] = newW.astype(np.asarray(d["obj_pose_world"]).dtype)
    newC = np.linalg.inv(c2w) @ newW
    d["fp_poses_cam"] = newC[:, None].astype(np.asarray(d["fp_poses_cam"]).dtype)
    with open(pkl, "wb") as f:
        pickle.dump(d, f, protocol=4)

    st = os.stat(pkl)
    marker = c / ".stages" / "05_object_pose.json"
    m = json.load(open(marker))
    hit = [o for o in m["outputs"] if Path(o["path"]).name == pkl.name]
    assert len(hit) == 1, f"stage-05 marker does not list {pkl.name} once"
    hit[0].update(size=int(st.st_size), mtime_ns=int(st.st_mtime_ns))
    json.dump(m, open(marker, "w"))

    report = {"max_gap": max_gap, "frames": n, "unreliable": int((~rel).sum()), "replaced_runs": replaced,
              "replaced_frames": int(sum(b - a for a, b in replaced)), "kept_runs_longer_than_max_gap": kept,
              "turn_deg_p50_p90_max_on_replaced": [round(float(v), 1) for v in np.percentile(turn[changed], [50, 90, 100])] if changed.any() else []}
    json.dump(report, open(c / "foundationpose" / "fp_init.json", "w"), indent=1)
    print(seq, {k: v for k, v in report.items() if not k.endswith("runs")}, flush=True)


if __name__ == "__main__":
    main()
