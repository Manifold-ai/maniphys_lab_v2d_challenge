"""Object dynamics post-process: an untouched object does not move, and its orientation is continuous (Tier 3 inputs only).

The dynamics check (gate/t3_dynamics_check.py) on the retargeted best_hm found every episode violating physics from its
first frames: unheld objects creeping and jittering at rest, and orientation jumps, many of them between equivalent
poses of a symmetric object. This rewrites the object's trajectory into the set those checks accept; the human is
untouched. Per episode, in this order:

  symmetry  the mesh's symmetry rotations are found from its shape (gate/t3_symmetry.py: n-fold or continuous turns
            about the principal axes that move no surface point by more than SYM_M there, as a closed set; the dynamics
            check uses the same rule). Until 10-15 this tested the mean shift, which accepted every 15 deg turn of the
            spray bottle and the mug about their axes; best_dyn4 and best_dyn5 were made that way. Frame by frame, the orientation is
            replaced by the equivalent one closest to the previous frame's, about the centre of mass, so the shape on
            screen is unchanged and only the orientation target becomes continuous.
  unheld    held comes from the physics check of the input version (a contact joint within HOLD_M: hands, plus feet
            when the task names a foot), with gaps shorter than GAP frames closed so a blink of the hand estimate does
            not split a grasp. Only unheld frames where the object rests are locked: those inside the input's
            resting placements (the anchors t3_height_post.py recorded in runs/<version>.height_post.json: static
            segments on the floor or on a support; for an input made by t3_depth_post.py, its runs/<version>.depth_post.json,
            same rows, added 10-16 for best_dr2s). Unheld and not resting means in the air, where a still pose would
            float; physically that is free fall, and in this data it is a hand or object estimate that broke for a few
            frames (ep17's cone 66 cm up at 0.8 m/s with the hand 28 cm away, ep19's cane turning 2.4 rad in 13
            frames), so those frames keep their motion and go with the held ones below; the dynamics check still
            reports them. Each locked run of at least MIN_RUN frames gets one pose: the centre of mass at its median,
            the orientation at the chordal mean, the height so that the lowest hull point sits at the run's median
            lowest point (the input already put that on its floor or support).
            With states=<dir> in place of the physics dir, the states are the dynamics check's own instead
            (gate/t3_contact_states.py on the input's retargeted reference): every run the check calls supported (not
            held by any robot hand link or the label, lowest point on the floor or a support) is locked, and nothing
            else. The human-layer held and the anchors judged a different object than the check does; frames one called
            held and the other unheld stayed unlocked, and the check measured them as drift (ep13, ep01, ep19; ep24 had no
            anchors at all and nothing was locked).
  held      a held run's ends would now jump to the locked neighbours. Each end's offset (position, and rotation by
            slerp) fades to zero over TAPER_S into the run (cosine), so the run meets the locked runs without a step
            and its middle keeps the input, where the hand holds it; a run shorter than 2 TAPER_S spreads the two
            offsets linearly over its length. At the episode's start or end nothing constrains the pose and that
            end's offset is zero. Until 10-15 every run spread its end offsets linearly over its whole length: ep07's
            two rests lost 5.8 and 4.7 cm of reconstruction drift when locked, and the 709 frames between them moved
            ~5 cm, away from the hand and off the image (IoU 0.863 -> 0.835); dyn5 had lost contacts the same way. Then the run's interior is
            smoothed (centre of mass by a local quadratic over WINDOW_S, orientation by a windowed chordal mean); the
            ends stay where the offsets put them, so the locked runs and the held ones meet without a step.
  outliers  the input's orientation jumps on single frames (the reconstruction flipping: ep03 turns 120 deg at frame
            448, ep28 140-174 deg several times). Until 10-15 every average above took those frames in, and invented
            poses the input never had: a 0.3 s window across ep03's flip laid the mug on its side (94-101 deg from the
            input at frame 451), and a rest run's mean over flipped frames left its held neighbour 143 deg to absorb
            (ep01). Now: a locked run's orientation is the mean of the frames within OUTLIER_DEG of its medoid, so flipped
            frames inside a rest are replaced, not averaged in (counted as rest_flips_replaced); the window mean takes
            only neighbours within OUTLIER_DEG of the frame itself (a flipped frame keeps its own pose); an end whose
            rotation offset exceeds MAX_OFFSET_DEG spreads its position offset only (rot_offsets_dropped). Every frame
            outside the locked runs then stays within MAX_OFFSET_DEG of its input orientation, which is asserted.
  floor     the offsets spread over a held run can carry the object below the floor; each frame is lifted along the
            floor normal until its lowest hull point is no lower than in the input or than the floor, whichever is
            lower (the input's own penetration is the height post-process's business, not this one's).

    python t3_dynamics_post.py <tier3 root> <version> <physics dir | states=<dir>> <out version> [episode,...]
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
from scipy.spatial.transform import Rotation, Slerp

FPS = 30.0
GAP = 5  # frames
MIN_RUN = 3  # frames
WINDOW_S = 0.3
OUTLIER_DEG = 20.0
MAX_OFFSET_DEG = 20.0
TAPER_S = 0.5  # an end's offset fades to zero over this much of the unlocked run (cosine)


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


def robust_mean(R, tol_deg=OUTLIER_DEG):
    """Chordal mean of the orientations within tol_deg of their medoid (the frame closest to all others)."""
    q = Rotation.from_matrix(R).as_quat()
    d = np.abs(q @ q.T).clip(0, 1)  # |cos(half angle)| between every pair
    med = int(np.argmax(d.sum(1)))
    keep = d[med] >= np.cos(np.deg2rad(tol_deg) / 2)
    return chordal_mean(R[keep]), int((~keep).sum())


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


def main() -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq
    import trimesh

    here = Path(__file__).resolve().parent
    sys.path[:0] = [str(here), str(here / "gate"), str(here.parents[2] / "libs" / "v2d_infra")]
    from tier_guard import forbid_lower_tiers
    forbid_lower_tiers()  # Tier 3: nothing from Tier 1 or Tier 2 (Kaggle 2.8.c)
    import t3_inputs  # imported here so t3_provenance sees every module this run uses
    import t3_provenance
    import t3_support  # noqa: F401
    import t3_symmetry  # noqa: F401

    root, version, src, out_v = Path(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4]
    states = Path(src.removeprefix("states=")) if src.startswith("states=") else None
    phys = None if states else Path(src)
    prov = t3_provenance.stamp([root / "input", root / "runs" / version, root / "runs" / f"{version}_suspect", states or phys])
    only = {int(x) for x in sys.argv[5].split(",")} if len(sys.argv) > 5 else None
    rn = root / "runs"
    if (rn / out_v).exists() or (rn / f"{out_v}_suspect").exists():
        raise SystemExit(f"runs/{out_v} exists; pick a new name")
    metas = {m["episode_index"]: m for m in map(json.loads, (root / "input/meta/episodes_metadata.jsonl").read_text().splitlines()) if m}
    win = int(round(WINDOW_S * FPS)) | 1
    anchors = {}
    if states is None:
        # the height post-process's anchors, or t3_depth_post.py's (same rows: start, end, kind) for a ray-corrected input
        rec = rn / f"{version}.height_post.json"
        rec = rec if rec.exists() else rn / f"{version}.depth_post.json"
        for row in json.loads(rec.read_text()):
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
            # "low" = the lowest hull point along the floor normal; the input version is already levelled, and the
            # normal is the one t3_height_post used, so read it the same way
            from t3_symmetry import SYM_M, Shape, nearest_equivalent, symmetries
            from t3_support import basis
            n_up, d_up, _, _, _ = basis(t3_inputs.ground_plane(root, m))
            low_of = lambda P, RR: (np.einsum("fij,kj->fki", RR, hull) + P[:, None]) @ n_up + d_up

            # 1. symmetry: continuous orientation among equivalent poses, centre of mass fixed
            shape = Shape(mesh, com_b)
            G, sym_axis = symmetries(shape, body.moment_inertia)
            com = pos + R @ com_b
            Rc = R.copy()
            if len(G) > 1 or sym_axis is not None:
                for t in range(1, n):
                    Rc[t] = nearest_equivalent(R[t], Rc[t - 1], G, sym_axis)
            sym_switch = int(sum(angle(R[t], Rc[t]) > np.deg2rad(1) for t in range(n)))
            for t in range(n):  # an equivalent pose moves no surface point by more than SYM_M (the 10-14 rule moved 3.4 cm)
                if angle(R[t], Rc[t]) > 1e-6 and shape.shift(R[t].T @ Rc[t]) > SYM_M:
                    raise SystemExit(f"{name}: frame {t}'s symmetric turn moves the surface {shape.shift(R[t].T @ Rc[t]):.4f} m")
            low0 = low_of(com - Rc @ com_b, Rc).min(1)

            # 2. unheld runs locked
            if states is not None:
                z = np.load(states / f"ep{ep:02d}.npz")
                held, resting = z["held"].astype(bool), z["supported"].astype(bool)
                if len(held) != n:
                    raise SystemExit(f"{name}: {len(held)} state frames for {n} pose frames")
            else:
                held = np.load(phys / "out" / f"{name}.npz")["held"].astype(bool)
                held = binary_closing(held, np.ones(2 * GAP + 1, bool)) | held
                if name not in anchors:
                    raise SystemExit(f"{name}: no height_post anchors for {version}")
                resting = np.zeros(n, bool)
                for a, b in anchors[name]:
                    resting[a:b] = True
            new_com, new_R = com.copy(), Rc.copy()
            locked = np.zeros(n, bool)
            lock_rows = []
            for a, b in runs(~held & resting):
                if b - a < MIN_RUN:
                    continue
                Rm, flips = robust_mean(Rc[a:b])
                cm = np.median(com[a:b], 0)
                l_now = (Rm @ (hull - com_b).T).T @ n_up + cm @ n_up + d_up
                cm = cm + (float(np.median(low0[a:b])) - l_now.min()) * n_up
                new_com[a:b], new_R[a:b] = cm, Rm
                locked[a:b] = True
                lock_rows.append({"start": a, "end": b, "drift_removed_m": round(float(np.linalg.norm(com[a:b] - cm, axis=1).max()), 4),
                                  "turn_removed_rad": round(max(angle(Rm, x) for x in Rc[a:b]), 3), "rest_flips_replaced": flips})

            # 3. held runs take the offsets, then are smoothed inside
            dropped = []
            for a, b in runs(~locked):
                d0 = (new_com[a - 1] - com[a - 1], new_R[a - 1] @ Rc[a - 1].T) if a > 0 else None
                d1 = (new_com[b] - com[b], new_R[b] @ Rc[b].T) if b < n else None
                zero = (np.zeros(3), np.eye(3))
                d0, d1 = d0 or zero, d1 or zero
                for k, d in ((0, d0), (1, d1)):  # a rotation offset this large is the rest's flip, not the grasp's
                    deg = float(np.degrees(angle(d[1], np.eye(3))))
                    if deg > MAX_OFFSET_DEG:
                        dropped.append({"run": [a, b], "end": "start" if k == 0 else "end", "deg": round(deg, 1)})
                        d0, d1 = ((d0[0], np.eye(3)), d1) if k == 0 else (d0, (d1[0], np.eye(3)))
                L, nt = b - a, int(round(TAPER_S * FPS))
                if L >= 2 * nt:  # each end's offset fades out near it; the middle keeps the input (and the hand)
                    i = np.arange(L, dtype=np.float64)
                    w0 = np.where(i < nt, 0.5 * (1 + np.cos(np.pi * (i + 1) / (nt + 1))), 0.0)
                    w1 = w0[::-1]
                    dp = w0[:, None] * d0[0] + w1[:, None] * d1[0]
                    r0 = Slerp([0, 1], Rotation.from_matrix([np.eye(3), d0[1]]))(w0).as_matrix()
                    r1 = Slerp([0, 1], Rotation.from_matrix([np.eye(3), d1[1]]))(w1).as_matrix()
                    dR = np.einsum("fij,fjk->fik", r1, r0)
                else:  # too short to fade both ends: spread linearly as before
                    w = np.linspace(0, 1, L + 2)[1:-1]
                    dp = (1 - w)[:, None] * d0[0] + w[:, None] * d1[0]
                    dR = Slerp([0, 1], Rotation.from_matrix([d0[1], d1[1]]))(w).as_matrix()
                c = com[a:b] + dp
                r = np.einsum("fij,fjk->fik", dR, Rc[a:b])
                if b - a > win:
                    c = savgol_filter(c, win, 2, axis=0, mode="interp")
                    half = win // 2
                    rs = r.copy()
                    for t in range(b - a):
                        nb = r[max(0, t - half):t + half + 1]
                        near = [x for x in nb if np.degrees(angle(x, r[t])) <= OUTLIER_DEG]
                        rs[t] = chordal_mean(np.asarray(near))
                    r = rs
                    c[0], c[-1], r[0], r[-1] = com[a] + dp[0], com[b - 1] + dp[-1], dR[0] @ Rc[a], dR[-1] @ Rc[b - 1]
                new_com[a:b], new_R[a:b] = c, r

            turn_out = np.degrees([angle(new_R[t], Rc[t]) for t in range(n)])
            bound = MAX_OFFSET_DEG + OUTLIER_DEG + 1e-6  # offset, then a window mean of neighbours within OUTLIER_DEG
            if (turn_out[~locked] > bound).any():
                t = int(np.flatnonzero(~locked)[np.argmax(turn_out[~locked])])
                raise SystemExit(f"{name}: frame {t} turned {turn_out[t]:.1f} deg from its input outside the locked runs")
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
            md[b"dynamics_post"] = json.dumps({"from": version, "symmetries": len(G), "continuous_axis": sym_axis is not None, "locked_runs": len(lock_rows)}).encode()
            out_t = out_t.replace_schema_metadata(md)
            dst = rn / dst_v / "data" / "chunk-000" / f.name
            dst.parent.mkdir(parents=True, exist_ok=True)
            pq.write_table(out_t, dst)
            (rn / dst_v / "meta").mkdir(exist_ok=True)
            mf = rn / src_v / "meta" / f"episode_{ep:06d}.metadata.json"
            (rn / dst_v / "meta" / mf.name).write_bytes(mf.read_bytes())

            step = np.linalg.norm(np.diff(new_com, axis=0), axis=1)
            row = {"episode": name, "tier": dst_v, "frames": n, "symmetries": len(G), "continuous_axis": sym_axis is not None, "symmetric_switch_frames": sym_switch,
                   "held_share": round(float(held.mean()), 3), "unheld_in_air_frames": int((~held & ~resting).sum()),
                   "floor_lifted_frames": int((lift > 0).sum()), "locked_share": round(float(locked.mean()), 3),
                   "locked_runs": lock_rows, "rot_offsets_dropped": dropped,
                   "unlocked_turn_from_input_deg_p99_max": [round(float(np.percentile(turn_out[~locked], 99)), 1) if (~locked).any() else 0.0,
                                                            round(float(turn_out[~locked].max()), 1) if (~locked).any() else 0.0],
                   "com_shift_m_p50_p95_max": [round(float(x), 4) for x in np.percentile(np.linalg.norm(new_com - com, axis=1), [50, 95, 100])],
                   "lowest_m_min_before_after": [round(float(low0.min()), 4), round(float(low1.min()), 4)],
                   "com_step_max_m": round(float(step.max()), 4)}
            report.append(row)
            print(json.dumps({k: v for k, v in row.items() if k != "locked_runs"}), flush=True)
    (rn / f"{out_v}.dynamics_post.json").write_text(json.dumps(report, indent=1))
    t3_provenance.write(rn / f"{out_v}.provenance.json", prov | {"made_by": "t3_dynamics_post.py", "from_version": version})


if __name__ == "__main__":
    main()
