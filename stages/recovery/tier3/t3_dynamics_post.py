"""Object dynamics post-process: an untouched object does not move, and its orientation is continuous (Tier 3 inputs only).

The dynamics check (gate/t3_dynamics_check.py) on the retargeted best_hm found every episode violating physics from its
first frames: unheld objects creeping and jittering at rest, and orientation jumps, many of them between equivalent
poses of a symmetric object. This rewrites the object's trajectory into the set those checks accept; the human is
untouched. Per episode, in this order:

  symmetry  the mesh's symmetry rotations are found from its shape (rotations about the principal axes, in SYM_STEP_DEG
            steps, that move the centred surface by less than SYM_M on average). Frame by frame, the orientation is
            replaced by the equivalent one closest to the previous frame's, about the centre of mass, so the shape on
            screen is unchanged and only the orientation target becomes continuous.
  unheld    held comes from the physics check of the input version (a contact joint within HOLD_M: hands, plus feet
            when the task names a foot), with gaps shorter than GAP frames closed so a blink of the hand estimate does
            not split a grasp. Only unheld frames where the object rests are locked: those inside the input's
            resting placements (the anchors t3_height_post.py recorded in runs/<version>.height_post.json: static
            segments on the floor or on a support). Unheld and not resting means in the air, where a still pose would
            float; physically that is free fall, and in this data it is a hand or object estimate that broke for a few
            frames (ep17's cone 66 cm up at 0.8 m/s with the hand 28 cm away, ep19's cane turning 2.4 rad in 13
            frames), so those frames keep their motion and go with the held ones below; the dynamics check still
            reports them. Each locked run of at least MIN_RUN frames gets one pose: the centre of mass at its median,
            the orientation at the chordal mean, the height so that the lowest hull point sits at the run's median
            lowest point (the input already put that on its floor or support).
  held      a held run's ends would now jump to the locked neighbours. The jump is spread over the run: the position
            offset and the rotation offset (slerp) go linearly from the one needed at its start to the one needed at
            its end; at the episode's start or end, where nothing constrains the pose, the offset is zero, so the
            run tapers back to the input (taking the single offset it has moved all of ep02's last 587 frames by
            the 12 cm a resting run before them lost). Then the run's interior is
            smoothed (centre of mass by a local quadratic over WINDOW_S, orientation by a windowed chordal mean); the
            ends stay where the offsets put them, so the locked runs and the held ones meet without a step.
  floor     the offsets spread over a held run can carry the object below the floor; each frame is lifted along the
            floor normal until its lowest hull point is no lower than in the input or than the floor, whichever is
            lower (the input's own penetration is the height post-process's business, not this one's).

    python t3_dynamics_post.py <tier3 root> <version> <physics dir> <out version> [episode,...]
Writes runs/<out version>{,_suspect}/ (same split as the input, only the listed episodes when given) and
runs/<out version>.dynamics_post.json.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from scipy.ndimage import binary_closing
from scipy.signal import savgol_filter
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation, Slerp

FPS = 30.0
GAP = 5  # frames
MIN_RUN = 3  # frames
WINDOW_S = 0.3
SYM_M = 0.01
SYM_REL = 0.05  # of the largest centre-to-surface distance, for small objects
SYM_STEP_DEG = 15


def to_R(q):  # wxyz -> matrices
    return Rotation.from_quat(np.c_[q[:, 1:4], q[:, 0:1]]).as_matrix()


def to_q(R):  # matrices -> wxyz
    x = Rotation.from_matrix(R).as_quat()
    return np.c_[x[:, 3:4], x[:, :3]]


def chordal_mean(R):
    u, _, vt = np.linalg.svd(R.mean(0))
    m = u @ vt
    if np.linalg.det(m) < 0:
        u[:, -1] *= -1
        m = u @ vt
    return m


def angle(a, b):
    return float(np.arccos(np.clip((np.trace(a.T @ b) - 1) / 2, -1, 1)))


def runs(mask):
    t, n, out = 0, len(mask), []
    while t < n:
        if mask[t]:
            s = t
            while t < n and mask[t]:
                t += 1
            out.append((s, t))
        else:
            t += 1
    return out


def symmetries(points, com, inertia):
    """Body-frame rotations (about the centre of mass) that leave the shape in place."""
    c = points - com
    tol = min(SYM_M, SYM_REL * float(np.linalg.norm(c, axis=1).max()))
    tree = cKDTree(c)
    _, axes = np.linalg.eigh(inertia)
    found = [np.eye(3)]
    for k in range(3):
        for deg in range(SYM_STEP_DEG, 360, SYM_STEP_DEG):
            g = Rotation.from_rotvec(axes[:, k] * np.deg2rad(deg)).as_matrix()
            if tree.query(c @ g.T)[0].mean() < tol and all(angle(g, f) > 1e-3 for f in found):
                found.append(g)
    return found


def main() -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq
    import trimesh

    root, version, phys, out_v = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3]), sys.argv[4]
    only = {int(x) for x in sys.argv[5].split(",")} if len(sys.argv) > 5 else None
    rn = root / "runs"
    if (rn / out_v).exists() or (rn / f"{out_v}_suspect").exists():
        raise SystemExit(f"runs/{out_v} exists; pick a new name")
    metas = {m["episode_index"]: m for m in map(json.loads, (root / "input/meta/episodes_metadata.jsonl").read_text().splitlines()) if m}
    win = int(round(WINDOW_S * FPS)) | 1
    anchors = {}
    for row in json.loads((rn / f"{version}.height_post.json").read_text()):
        anchors[row["episode"]] = [(a["start"], a["end"]) for a in row["anchors"]]
    report = []
    for src_v, dst_v in ((version, out_v), (f"{version}_suspect", f"{out_v}_suspect")):
        for f in sorted((rn / src_v / "data" / "chunk-000").glob("episode_*.parquet")):
            table = pq.read_table(f)
            ep = int(table.column("episode_index")[0].as_py())
            if only and ep not in only:
                continue
            m = metas[ep]
            name = f"ep{ep:02d}_{m['object']}"
            pose = np.stack(table.column("observation.object.pose").to_numpy(zero_copy_only=False)).astype(np.float64)
            pos, R = pose[:, :3], to_R(pose[:, 3:7])
            n = len(pos)
            mesh = trimesh.load(root / "input" / m["mesh"], force="mesh")
            body = mesh if mesh.is_watertight else mesh.convex_hull
            com_b = np.asarray(body.center_mass)
            hull = np.asarray(mesh.convex_hull.vertices, np.float64)
            surf = np.asarray(mesh.vertices, np.float64)
            surf = surf[np.random.default_rng(0).choice(len(surf), min(len(surf), 2000), replace=False)]
            # "low" = the lowest hull point along the floor normal; the input version is already levelled, and the
            # normal is the one t3_height_post used, so read it the same way
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            import t3_inputs
            from t3_support import basis
            n_up, d_up, _, _, _ = basis(t3_inputs.ground_plane(root, m))
            low_of = lambda P, RR: (np.einsum("fij,kj->fki", RR, hull) + P[:, None]) @ n_up + d_up

            # 1. symmetry: continuous orientation among equivalent poses, centre of mass fixed
            G = symmetries(surf, com_b, np.asarray(body.moment_inertia))
            com = pos + R @ com_b
            Rc = R.copy()
            sym_switch = 0
            for t in range(1, n):
                cands = [R[t] @ g for g in G]
                best = int(np.argmin([angle(Rc[t - 1], c) for c in cands]))
                sym_switch += int(best != 0)
                Rc[t] = cands[best]
            low0 = low_of(com - Rc @ com_b, Rc).min(1)

            # 2. unheld runs locked
            held = np.load(phys / "out" / f"{name}.npz")["held"].astype(bool)
            held = binary_closing(held, np.ones(2 * GAP + 1, bool)) | held
            new_com, new_R = com.copy(), Rc.copy()
            locked = np.zeros(n, bool)
            lock_rows = []
            if name not in anchors:
                raise SystemExit(f"{name}: no height_post anchors for {version}")
            resting = np.zeros(n, bool)
            for a, b in anchors[name]:
                resting[a:b] = True
            for a, b in runs(~held & resting):
                if b - a < MIN_RUN:
                    continue
                Rm = chordal_mean(Rc[a:b])
                cm = np.median(com[a:b], 0)
                l_now = (Rm @ (hull - com_b).T).T @ n_up + cm @ n_up + d_up
                cm = cm + (float(np.median(low0[a:b])) - l_now.min()) * n_up
                new_com[a:b], new_R[a:b] = cm, Rm
                locked[a:b] = True
                lock_rows.append({"start": a, "end": b, "drift_removed_m": round(float(np.linalg.norm(com[a:b] - cm, axis=1).max()), 4),
                                  "turn_removed_rad": round(max(angle(Rm, x) for x in Rc[a:b]), 3)})

            # 3. held runs take the offsets, then are smoothed inside
            for a, b in runs(~locked):
                d0 = (new_com[a - 1] - com[a - 1], new_R[a - 1] @ Rc[a - 1].T) if a > 0 else None
                d1 = (new_com[b] - com[b], new_R[b] @ Rc[b].T) if b < n else None
                zero = (np.zeros(3), np.eye(3))
                d0, d1 = d0 or zero, d1 or zero
                w = np.linspace(0, 1, b - a + 2)[1:-1]
                dp = (1 - w)[:, None] * d0[0] + w[:, None] * d1[0]
                dR = Slerp([0, 1], Rotation.from_matrix([d0[1], d1[1]]))(w).as_matrix()
                c = com[a:b] + dp
                r = np.einsum("fij,fjk->fik", dR, Rc[a:b])
                if b - a > win:
                    c = savgol_filter(c, win, 2, axis=0, mode="interp")
                    half = win // 2
                    rs = r.copy()
                    for t in range(b - a):
                        rs[t] = chordal_mean(r[max(0, t - half):t + half + 1])
                    r = rs
                    c[0], c[-1], r[0], r[-1] = com[a] + dp[0], com[b - 1] + dp[-1], dR[0] @ Rc[a], dR[-1] @ Rc[b - 1]
                new_com[a:b], new_R[a:b] = c, r

            low1 = low_of(new_com - new_R @ com_b, new_R).min(1)
            lift = np.maximum(0.0, np.minimum(low0, 0.0) - low1)
            new_com = new_com + lift[:, None] * n_up
            new_pos = new_com - new_R @ com_b
            low1 = low_of(new_pos, new_R).min(1)
            out = pose.copy()
            out[:, :3], out[:, 3:7] = new_pos, to_q(new_R)
            col = pa.FixedSizeListArray.from_arrays(pa.array(out.astype(np.float32).ravel(), pa.float32()), 7)
            i = table.schema.get_field_index("observation.object.pose")
            out_t = table.set_column(i, table.schema.field(i), col)
            md = dict(out_t.schema.metadata or {})
            md[b"dynamics_post"] = json.dumps({"from": version, "symmetries": len(G), "locked_runs": len(lock_rows)}).encode()
            out_t = out_t.replace_schema_metadata(md)
            dst = rn / dst_v / "data" / "chunk-000" / f.name
            dst.parent.mkdir(parents=True, exist_ok=True)
            pq.write_table(out_t, dst)
            (rn / dst_v / "meta").mkdir(exist_ok=True)
            mf = rn / src_v / "meta" / f"episode_{ep:06d}.metadata.json"
            (rn / dst_v / "meta" / mf.name).write_bytes(mf.read_bytes())

            step = np.linalg.norm(np.diff(new_com, axis=0), axis=1)
            row = {"episode": name, "tier": dst_v, "frames": n, "symmetries": len(G), "symmetric_switch_frames": sym_switch,
                   "held_share": round(float(held.mean()), 3), "unheld_in_air_frames": int((~held & ~resting).sum()),
                   "floor_lifted_frames": int((lift > 0).sum()), "locked_share": round(float(locked.mean()), 3),
                   "locked_runs": lock_rows,
                   "com_shift_m_p50_p95_max": [round(float(x), 4) for x in np.percentile(np.linalg.norm(new_com - com, axis=1), [50, 95, 100])],
                   "lowest_m_min_before_after": [round(float(low0.min()), 4), round(float(low1.min()), 4)],
                   "com_step_max_m": round(float(step.max()), 4)}
            report.append(row)
            print(json.dumps({k: v for k, v in row.items() if k != "locked_runs"}), flush=True)
    (rn / f"{out_v}.dynamics_post.json").write_text(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
