"""Choose FoundationPose's per-frame pose over the whole timeline from its dumped candidates (runs in the v2d_cari4d image).

Why: the exporter picks each frame's pose next to the previously confirmed one, so a wrong branch, once picked, is
followed for whole segments, and CoCoNet (stage 06) follows that initialization (handoff-tier3-rotation-2026-10-16.md,
10-16 initialization pilot). The 10-16 pilot slerped across FoundationPose's "unreliable" runs, but "reliable" only
means "continuous with the previous confirmed pose", so both ends of a run can be on the wrong branch, long runs were
skipped and confidently wrong frames were never touched. Here no frame is trusted: every frame chooses among its own
candidates (t3_fp_dump.sh, third_party/patches/cari4d-fp-candidate-dump.patch), jointly with its neighbours (Viterbi).

States of a frame: the shortlist candidates of all its registration calls (they passed the exporter's relaxed silhouette
screen and carry full-image IoU); a frame whose shortlists are all empty falls back to each call's TOP_K by FP score,
with the IoU term neutral. Frames without a call (too little visible object) are not states; they carry the last
chosen pose, as the exporter carries its last confirmed one.
Unary (lower is better): -(score_logp + W_IOU * iou), score_logp = the FP score's log-softmax within its own call (the
depth- and RGB-refined pools have different scales, so scores are compared only inside a call).
Pairwise between consecutive states (g = frames between them, >= 1): angle / (ROT_DEG * g) + |dt| / (TRANS_M * g),
the angle taken over the object's symmetry rotations (gate/t3_symmetry.py, from the official mesh as t3_dynamics_post.py).
The parameters were fixed on 10-19 before any pilot result and are not tuned on the checked frames, which the gate
uses as its answer key (stages/recovery/tier3/checked_frames.json, evaluation only).

Writes the chosen poses into the stage-05 pkl in place (fp_poses_cam, obj_pose_world; other keys kept, the stage-06
loader validates them) and updates the stage-05 marker's output identity so the runner reuses stage 05 and reruns 06
onward, as t3_fp_init.py; the report goes to foundationpose/fp_select.json.

    python t3_fp_select.py <cari4d episode dir> <candidates.npz> <official mesh> [--dry]
"""

import json
import os
import pickle
import sys
from pathlib import Path

import numpy as np
import trimesh

sys.path.insert(0, str(Path(__file__).resolve().parent / "gate"))
from t3_symmetry import Shape, symmetries  # noqa: E402

W_IOU = 5.0
ROT_DEG = 10.0
TRANS_M = 0.05
TOP_K = 8
PARAMS = {"W_IOU": W_IOU, "ROT_DEG": ROT_DEG, "TRANS_M": TRANS_M, "TOP_K": TOP_K}


def log_softmax(s):
    s = np.asarray(s, np.float64)
    m = s.max()
    return s - m - np.log(np.exp(s - m).sum())


def sym_angle_deg(Ra, Rb, G, axis):
    """(len(Ra), len(Rb)) smallest angle between Ra[i] and Rb[j] g over the symmetry rotations g (and a turn about the
    continuous axis, closed form as t3_symmetry.nearest_equivalent)."""
    M = np.einsum("aji,bjk->abik", Ra, Rb)  # Ra^T Rb
    best = np.full(M.shape[:2], np.inf)
    for g in G:
        C = M @ g
        if axis is None:
            tr = np.trace(C, axis1=2, axis2=3)
        else:
            a = np.asarray(axis, np.float64)
            ax = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
            t1 = np.einsum("abij,ji->ab", C, ax)
            t0 = np.trace(C, axis1=2, axis2=3) - np.einsum("i,abij,j->ab", a, C, a)
            # trace(C Rot(a, phi)) = a^T C a + cos(phi) t0 + sin(phi) t1, maximised at |(t0, t1)|
            tr = np.einsum("i,abij,j->ab", a, C, a) + np.hypot(t0, t1)
        best = np.minimum(best, np.degrees(np.arccos(np.clip((tr - 1) / 2, -1, 1))))
    return best


def states_of(c, f, calls):
    """Candidate camera poses (source mesh frame is applied by the caller), unary costs and a provenance tag per state."""
    poses, unary, tag = [], [], []
    shortlisted = False
    for i in calls:
        a, b = c["call_offsets"][i], c["call_offsets"][i + 1]
        lp = log_softmax(c["scores"][a:b])
        ids = c["source_ids"][a:b]
        sa, sb = c["shortlist_offsets"][i], c["shortlist_offsets"][i + 1]
        for sid, iou in zip(c["shortlist_source_ids"][sa:sb], c["shortlist_iou"][sa:sb]):
            j = np.flatnonzero(ids == sid)
            if len(j) != 1 or not np.isfinite(iou):
                continue
            shortlisted = True
            poses.append(c["poses_centered"][a + j[0]] @ c["call_transform_to_centered"][i])
            unary.append(-(lp[j[0]] + W_IOU * float(iou)))
            tag.append((int(i), int(sid)))
    if not shortlisted:
        for i in calls:
            a, b = c["call_offsets"][i], c["call_offsets"][i + 1]
            lp = log_softmax(c["scores"][a:b])
            for j in range(min(TOP_K, b - a)):
                poses.append(c["poses_centered"][a + j] @ c["call_transform_to_centered"][i])
                unary.append(-(lp[j] + W_IOU * 0.5))
                tag.append((int(i), int(c["source_ids"][a + j])))
    return np.asarray(poses, np.float64), np.asarray(unary), tag, shortlisted


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry" in sys.argv
    ep_dir, cand_path, mesh_path = Path(args[0]), Path(args[1]), Path(args[2])
    (pkl,) = sorted((ep_dir / "foundationpose").glob("episode_*.pkl"))
    seq = pkl.stem
    d = pickle.load(open(pkl, "rb"))
    # read every array once: an NpzFile decompresses the whole array on each c[key], and the loops below index it per
    # frame and per candidate (10-19: the first ep04 run did not finish in 11 minutes)
    with np.load(cand_path) as z:
        c = {k: z[k] for k in z.files}
    if list(c["frames"]) != list(d["frames"]):
        raise SystemExit("candidates and pkl cover different frames")
    export = json.loads((ep_dir / "export" / seq / "wild_export.json").read_text())
    s2a = np.asarray(export["source_object_mesh_to_aligned_transform"], np.float64)

    mesh = trimesh.load(mesh_path, force="mesh")
    body = mesh if mesh.is_watertight else mesh.convex_hull
    G, axis = symmetries(Shape(mesh, np.asarray(body.center_mass)), body.moment_inertia)

    W0 = np.asarray(d["obj_pose_world"], np.float64)
    C0 = np.asarray(d["fp_poses_cam"], np.float64)[:, 0]
    c2w = W0 @ np.linalg.inv(C0)
    n = len(C0)
    frames = [f for f in range(n) if (c["call_frame"] == f).any()]
    S = []
    for f in frames:
        P, u, tag, sl = states_of(c, f, np.flatnonzero(c["call_frame"] == f))
        Ps = P @ s2a  # source mesh frame, where the symmetry rotations live
        S.append({"f": f, "P": P, "R": Ps[:, :3, :3], "t": P[:, :3, 3], "u": u, "tag": tag, "shortlisted": sl})

    # Viterbi
    cost = S[0]["u"].copy()
    back = []
    for k in range(1, len(S)):
        a, b = S[k - 1], S[k]
        gap = b["f"] - a["f"]
        ang = sym_angle_deg(a["R"], b["R"], G, axis)
        dt = np.linalg.norm(a["t"][:, None] - b["t"][None], axis=2)
        tot = cost[:, None] + ang / (ROT_DEG * gap) + dt / (TRANS_M * gap)
        back.append(tot.argmin(0))
        cost = tot.min(0) + b["u"]
    pick = [int(cost.argmin())]
    for bp in reversed(back):
        pick.append(int(bp[pick[-1]]))
    pick = pick[::-1]

    newC = C0.copy()
    chosen = {}
    for st, j in zip(S, pick):
        newC[st["f"]] = st["P"][j]
        chosen[st["f"]] = j
    last = None
    for f in range(n):  # frames without a call carry the last chosen pose (before the first: the first chosen)
        if f in chosen:
            last = newC[f]
        elif last is not None:
            newC[f] = last
    first = newC[frames[0]]
    for f in range(frames[0]):
        newC[f] = first
    newW = c2w @ newC

    R0s, R1s = (C0 @ s2a)[:, :3, :3], (newC @ s2a)[:, :3, :3]
    turn = np.array([sym_angle_deg(R0s[f:f + 1], R1s[f:f + 1], G, axis)[0, 0] for f in range(n)])
    moved = np.linalg.norm(newC[:, :3, 3] - C0[:, :3, 3], axis=1)
    jump = lambda R: np.array([sym_angle_deg(R[f:f + 1], R[f + 1:f + 2], G, axis)[0, 0] for f in range(n - 1)])
    report = {"params": PARAMS, "frames": n, "frames_with_calls": len(frames),
              "frames_without_shortlist": int(sum(not s["shortlisted"] for s in S)),
              "states_p50_max": [int(np.median([len(s["u"]) for s in S])), int(max(len(s["u"]) for s in S))],
              "symmetry": {"discrete": len(G), "continuous_axis": None if axis is None else [round(float(v), 4) for v in axis]},
              "changed_gt24_deg": int((turn > 24).sum()), "turn_deg_p50_p90_max": [round(float(v), 1) for v in np.percentile(turn, [50, 90, 100])],
              "moved_m_p50_p90_max": [round(float(v), 4) for v in np.percentile(moved, [50, 90, 100])],
              "jumps_gt24_before_after": [int((jump(R0s) > 24).sum()), int((jump(R1s) > 24).sum())],
              "turn_deg": [round(float(v), 2) for v in turn]}
    print(seq, json.dumps({k: v for k, v in report.items() if k != "turn_deg"}), flush=True)
    if dry:
        return
    d["obj_pose_world"] = newW.astype(np.asarray(d["obj_pose_world"]).dtype)
    d["fp_poses_cam"] = newC[:, None].astype(np.asarray(d["fp_poses_cam"]).dtype)
    with open(pkl, "wb") as fh:
        pickle.dump(d, fh, protocol=4)
    st = os.stat(pkl)
    marker = ep_dir / ".stages" / "05_object_pose.json"
    m = json.load(open(marker))
    hit = [o for o in m["outputs"] if Path(o["path"]).name == pkl.name]
    assert len(hit) == 1, f"stage-05 marker does not list {pkl.name} once"
    hit[0].update(size=int(st.st_size), mtime_ns=int(st.st_mtime_ns))
    json.dump(m, open(marker, "w"))
    json.dump(report, open(ep_dir / "foundationpose" / "fp_select.json", "w"), indent=1)


if __name__ == "__main__":
    main()
