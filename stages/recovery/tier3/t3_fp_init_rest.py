"""CoCoNet's object initialization anchored on whole rest segments, not on two neighbouring reliable frames (pilot, 10-17;
runs in the v2d_cari4d image).

Why: t3_fp_init.py slerped each unreliable run between the reliable frames on its two sides. `fp_reliable` only says
"consistent with the previous confirmed pose", so those two frames can sit on a wrong branch, runs over 60 frames were
skipped, and FoundationPose's confident errors are not in an unreliable run at all (rxzhou 10-16; ep03 frame 451).
Here an object changes orientation only while it moves: on a rest segment (the object static, on the floor or a support;
the anchors t3_depth_post.py recorded for the version, frame ranges only) it has one orientation, voted by the whole
segment. Moving stretches (held, or kicked and sliding, as ep29's luggage) connect the rest orientations around them by
the least total rotation over per-frame hypotheses: FoundationPose's pose and its three 180-degree turns about the mesh's
principal axes (the head-to-tail flips a silhouette cannot tell apart), a flip costing FLIP_DEG (reliable frame) or
FLIP_UNREL_DEG (unreliable frame) of rotation, solved exactly by dynamic programming with both ends pinned to the
neighbouring rest orientations (one end at the start or end of the episode).
  rest vote  the frame whose orientation has the most frames of the segment within VOTE_DEG wins; the segment gets the
             chordal mean of those inliers.
Positions stay where FoundationPose put the mesh's bounds centre (as t3_fp_init.py). The pkl keeps its keys, the stage-05
marker is updated so stage 05 is reused, what changed goes to foundationpose/fp_init.json (method rest_anchor).

    python t3_fp_init_rest.py <cari4d episode dir> <depth_post.json> <episode name> [--dry]
--dry writes nothing and prints the per-segment choice.
"""

import json
import os
import pickle
import sys
from pathlib import Path

import numpy as np
import trimesh

VOTE_DEG = 15.0
FLIP_DEG = 10.0
FLIP_UNREL_DEG = 2.0


def angle(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Rotation angle (deg) between rotation stacks a and b (broadcast over leading axes)."""
    return np.degrees(np.arccos(np.clip((np.einsum("...ij,...ij->...", a, b) - 1) / 2, -1, 1)))


def flips(mesh: trimesh.Trimesh) -> np.ndarray:
    """Identity and the half turns about the mesh's principal axes, in the object frame (right-multiplied)."""
    ax = np.asarray(mesh.principal_inertia_vectors, np.float64)
    return np.stack([np.eye(3)] + [2 * np.outer(a, a) / (a @ a) - np.eye(3) for a in ax])


def rest_orientation(R: np.ndarray) -> tuple[np.ndarray, int]:
    A = angle(R[:, None], R[None])
    votes = (A < VOTE_DEG).sum(1)
    inl = A[int(np.argmax(votes))] < VOTE_DEG
    u, _, vt = np.linalg.svd(R[inl].sum(0))
    m = u @ vt
    if np.linalg.det(m) < 0:
        u[:, -1] *= -1
        m = u @ vt
    return m, int(inl.sum())


def connect(R: np.ndarray, rel: np.ndarray, G: np.ndarray, left: np.ndarray | None, right: np.ndarray | None) -> np.ndarray:
    """Hypothesis index per frame minimising total rotation + flip costs, ends pinned to left / right (or free)."""
    H = np.einsum("tij,sjk->tsik", R, G)  # (t, 4, 3, 3)
    emit = np.where(np.arange(len(G))[None] == 0, 0.0, np.where(rel[:, None], FLIP_DEG, FLIP_UNREL_DEG))
    cost = emit[0] + (angle(H[0], left[None]) if left is not None else 0.0)
    back = []
    for t in range(1, len(R)):
        step = cost[:, None] + angle(H[t - 1][:, None], H[t][None])  # (prev, cur)
        back.append(np.argmin(step, 0))
        cost = step.min(0) + emit[t]
    if right is not None:
        cost = cost + angle(H[-1], right[None])
    s = [int(np.argmin(cost))]
    for b in reversed(back):
        s.append(int(b[s[-1]]))
    return np.array(s[::-1])


def main():
    args = [a for a in sys.argv[1:] if a != "--dry"]
    dry = "--dry" in sys.argv
    c, anchors_json, name = Path(args[0]), Path(args[1]), args[2]
    pkl = next((c / "foundationpose").glob("episode_*.pkl"))
    seq = pkl.stem
    d = pickle.load(open(pkl, "rb"))
    W = np.asarray(d["obj_pose_world"], np.float64)
    C = np.asarray(d["fp_poses_cam"], np.float64)[:, 0]
    ok = np.isfinite(W).all((1, 2))
    rel = np.asarray(d["fp_reliable"], bool) & ok
    n = len(W)
    mesh = trimesh.load(c / "export" / seq / "object_mesh" / "output_aligned.glb", force="mesh")
    centre, G = mesh.bounds.mean(0), flips(mesh)
    row = next(r for r in json.loads(anchors_json.read_text()) if r["episode"] == name)
    rests = sorted((int(a["start"]), min(int(a["end"]), n)) for a in row["anchors"])

    R0 = W[:, :3, :3].copy()
    newR = R0.copy()
    segs = []
    rest_R = []
    for a, b in rests:
        idx = np.arange(a, b)[ok[a:b]]
        if len(idx) == 0:
            rest_R.append(None)
            continue
        m, k = rest_orientation(R0[idx])
        newR[idx] = m
        rest_R.append(m)
        segs.append({"kind": "rest", "frames": [a, b], "inliers": k, "of": len(idx),
                     "turned_frames": int((angle(R0[idx], m[None]) > VOTE_DEG).sum())})
    bounds = [(0, None, rests[0][0] if rests else n, rest_R[0] if rests else None)]
    for i in range(len(rests) - 1):
        bounds.append((rests[i][1], rest_R[i], rests[i + 1][0], rest_R[i + 1]))
    if rests:
        bounds.append((rests[-1][1], rest_R[-1], n, None))
    for a, left, b, right in bounds:
        if b - a <= 0:
            continue
        idx = np.arange(a, b)[ok[a:b]]
        if len(idx) == 0:
            continue
        s = connect(R0[idx], rel[idx], G, left, right)
        newR[idx] = np.einsum("tij,tjk->tik", R0[idx], G[s])
        segs.append({"kind": "moving", "frames": [int(a), int(b)], "pinned": [left is not None, right is not None],
                     "flipped_frames": int((s > 0).sum()), "flip_runs": int(np.count_nonzero(np.diff(np.r_[0, (s > 0).astype(int), 0]) == 1))})
    turn = angle(newR, R0)
    newW = W.copy()
    newW[:, :3, :3] = newR
    newW[:, :3, 3] = W[:, :3, :3] @ centre + W[:, :3, 3] - newR @ centre
    report = {"method": "rest_anchor", "frames": n, "rests": len(rests), "vote_deg": VOTE_DEG, "flip_deg": FLIP_DEG,
              "flip_unrel_deg": FLIP_UNREL_DEG, "changed_frames": int((turn > 1e-6).sum()),
              "turn_deg_p50_p90_max_on_changed": [round(float(v), 1) for v in np.percentile(turn[turn > 1e-6], [50, 90, 100])] if (turn > 1e-6).any() else [],
              "segments": segs}
    if dry:
        print(json.dumps(report))
        return
    d["obj_pose_world"] = newW.astype(np.asarray(d["obj_pose_world"]).dtype)
    d["fp_poses_cam"] = (np.linalg.inv(W @ np.linalg.inv(C)) @ newW)[:, None].astype(np.asarray(d["fp_poses_cam"]).dtype)
    with open(pkl, "wb") as f:
        pickle.dump(d, f, protocol=4)
    st = os.stat(pkl)
    marker = c / ".stages" / "05_object_pose.json"
    m = json.load(open(marker))
    hit = [o for o in m["outputs"] if Path(o["path"]).name == pkl.name]
    assert len(hit) == 1, f"stage-05 marker does not list {pkl.name} once"
    hit[0].update(size=int(st.st_size), mtime_ns=int(st.st_mtime_ns))
    json.dump(m, open(marker, "w"))
    json.dump(report, open(c / "foundationpose" / "fp_init.json", "w"), indent=1)
    print(seq, {k: v for k, v in report.items() if k != "segments"}, flush=True)


if __name__ == "__main__":
    main()
