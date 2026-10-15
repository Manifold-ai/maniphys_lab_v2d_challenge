"""Object trajectory smoothing by a contact-switched Kalman filter and RTS smoother (Tier 3 inputs only; trial, 10-15).

t3_dynamics_post.py fixes the object with hand-written rules (lock rests to one pose, spread the offsets over grasps,
window means), and each rule needed its own guard against the reconstruction's single-frame flips. This replaces the
rules with one model, run forward then backward over the whole episode:

  state      centre of mass and its velocity (constant velocity); orientation and body angular velocity (an
             error-state filter on SO(3): the orientation is kept as a matrix, corrections are rotation vectors).
  modes      rest (not held and inside a height_post resting placement, as t3_dynamics_post) or moving. At rest the
             process noise is small and a zero-velocity pseudo-observation is added for both velocities (a resting
             body does not move), which takes the place of locking. Moving: accelerations up to A_MOVE / ALPHA_MOVE.
  observe    each frame's pose. Position noise is anisotropic: SIGMA_RAY_REL of the camera distance along the viewing
             ray (monocular depth, t3_depth_diag: 1-3 % at rest), SIGMA_PERP across it. Orientation SIGMA_ROT.
  outliers   an observation whose Mahalanobis distance from the prediction exceeds GATE_CHI2 (chi-square, 3 dof),
             or whose orientation is more than GATE_DEG from it, is not used: the flip is bridged by the model.
             After RESET_AFTER rejected frames in a row the filter restarts from the observation, so a real fast
             move the model did not expect is not rejected for the rest of the episode (counted as resets). A reset
             starts a new segment that the backward pass does not cross (ep01's multi-frame flips: smoothing across a
             160 deg reset put a used frame 162 deg off its observation). Which side of a multi-frame flip is right
             the trajectory cannot tell; that needs the image (render both, compare with the video), not done here.
  smooth     Rauch-Tung-Striebel backward pass (on the error state for the orientation).
  floor      no frame's lowest hull point lower than in the input or than the floor, whichever is lower (as
             t3_dynamics_post's last step).

The camera centre comes from each episode's convert dir (the world step's similarity, as t3_align_check.py), chosen by
the version's selection json. Symmetric objects first get continuous equivalent orientations (t3_symmetry, as
t3_dynamics_post step 1). Asserted: on frames whose observation was used, the output orientation stays within
GATE_DEG of it.

    python t3_kalman_post.py <tier3 root> <version> <physics dir> <selection json> <out version> [episode,...]
Writes runs/<out version>{,_suspect}/, runs/<out version>.kalman_post.json and .provenance.json.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from scipy.ndimage import binary_closing
from scipy.spatial.transform import Rotation

FPS = 30.0
DT = 1.0 / FPS
GAP = 5  # frames, held gaps closed as t3_dynamics_post
SIGMA_PERP = 0.01  # m
SIGMA_RAY_REL = 0.017
SIGMA_ROT = np.deg2rad(3.0)
A_REST, A_MOVE = 0.05, 10.0  # m/s^2, white acceleration noise
ALPHA_REST, ALPHA_MOVE = 0.2, 30.0  # rad/s^2
SIGMA_ZV, SIGMA_ZW = 0.005, 0.02  # zero-velocity pseudo-observation, m/s and rad/s
GATE_CHI2 = 16.27  # chi-square 3 dof, 0.999
GATE_DEG = 30.0
RESET_AFTER = 5


def exp_so3(v):
    return Rotation.from_rotvec(v).as_matrix()


def log_so3(R):
    return Rotation.from_matrix(R).as_rotvec()


def cv_model(q):
    """Constant-velocity transition and white-acceleration process noise for one 3-D quantity (6 x 6)."""
    I = np.eye(3)
    F = np.block([[I, DT * I], [np.zeros((3, 3)), I]])
    Q = q ** 2 * np.block([[DT ** 4 / 4 * I, DT ** 3 / 2 * I], [DT ** 3 / 2 * I, DT ** 2 * I]])
    return F, Q


def update(x, P, y, H, Rn):
    S = H @ P @ H.T + Rn
    K = P @ H.T @ np.linalg.inv(S)
    return x + K @ y, (np.eye(len(x)) - K @ H) @ P, float(y @ np.linalg.solve(S, y))


def smooth_position(z, rest, cam):
    n = len(z)
    H = np.hstack([np.eye(3), np.zeros((3, 3))])
    Hv = np.hstack([np.zeros((3, 3)), np.eye(3)])
    xf, Pf, xp, Pp = np.zeros((n, 6)), np.zeros((n, 6, 6)), np.zeros((n, 6)), np.zeros((n, 6, 6))
    x, P = np.r_[z[0], np.zeros(3)], np.diag([0.05 ** 2] * 3 + [1.0] * 3)
    used, resets, streak = np.zeros(n, bool), 0, 0
    cut = np.zeros(n, bool)  # a reset starts a new segment; the backward pass does not cross it
    for t in range(n):
        if t:
            F, Q = cv_model(A_REST if rest[t] else A_MOVE)
            x, P = F @ x, F @ P @ F.T + Q
        xp[t], Pp[t] = x, P
        u = z[t] - cam
        u /= np.linalg.norm(u)
        d = np.linalg.norm(z[t] - cam)
        Rn = SIGMA_PERP ** 2 * np.eye(3) + ((SIGMA_RAY_REL * d) ** 2 - SIGMA_PERP ** 2) * np.outer(u, u)
        y = z[t] - H @ x
        S = H @ P @ H.T + Rn
        if t == 0 or float(y @ np.linalg.solve(S, y)) <= GATE_CHI2:
            x, P, _ = update(x, P, y, H, Rn)
            used[t], streak = True, 0
        else:
            streak += 1
            if streak >= RESET_AFTER:
                x, P = np.r_[z[t], x[3:]], np.diag([0.05 ** 2] * 3 + [1.0] * 3)
                used[t], streak, resets, cut[t] = True, 0, resets + 1, True
        if rest[t]:
            x, P, _ = update(x, P, -x[3:], Hv, SIGMA_ZV ** 2 * np.eye(3))
        xf[t], Pf[t] = x, P
    xs = xf.copy()
    Ps = Pf.copy()
    for t in range(n - 2, -1, -1):
        if cut[t + 1]:
            continue  # xs[t] stays the filtered estimate: the next segment does not inform this one
        F, _ = cv_model(A_REST if rest[t + 1] else A_MOVE)
        C = Pf[t] @ F.T @ np.linalg.inv(Pp[t + 1])
        xs[t] = xf[t] + C @ (xs[t + 1] - xp[t + 1])
        Ps[t] = Pf[t] + C @ (Ps[t + 1] - Pp[t + 1]) @ C.T
    return xs[:, :3], used, resets


def smooth_rotation(Z, rest):
    n = len(Z)
    H = np.hstack([np.eye(3), np.zeros((3, 3))])
    Hw = np.hstack([np.zeros((3, 3)), np.eye(3)])
    Rf, wf, Pf = np.zeros((n, 3, 3)), np.zeros((n, 3)), np.zeros((n, 6, 6))
    Rp, wp, Pp = np.zeros((n, 3, 3)), np.zeros((n, 3)), np.zeros((n, 6, 6))
    R, w, P = Z[0].copy(), np.zeros(3), np.diag([SIGMA_ROT ** 2] * 3 + [1.0] * 3)
    used, resets, streak = np.zeros(n, bool), 0, 0
    cut = np.zeros(n, bool)
    Rn = SIGMA_ROT ** 2 * np.eye(3)
    for t in range(n):
        if t:
            F, Q = cv_model(ALPHA_REST if rest[t] else ALPHA_MOVE)
            R, P = R @ exp_so3(w * DT), F @ P @ F.T + Q
        Rp[t], wp[t], Pp[t] = R, w, P
        y = log_so3(R.T @ Z[t])
        S = H @ P @ H.T + Rn
        ok = t == 0 or (float(y @ np.linalg.solve(S, y)) <= GATE_CHI2 and np.degrees(np.linalg.norm(y)) <= GATE_DEG)
        if ok:
            dx, P, _ = update(np.zeros(6), P, y, H, Rn)
            R, w, used[t], streak = R @ exp_so3(dx[:3]), w + dx[3:], True, 0
        else:
            streak += 1
            if streak >= RESET_AFTER:
                R, w, P = Z[t].copy(), np.zeros(3), np.diag([SIGMA_ROT ** 2] * 3 + [1.0] * 3)
                used[t], streak, resets, cut[t] = True, 0, resets + 1, True
        if rest[t]:
            dx, P, _ = update(np.zeros(6), P, -w, Hw, SIGMA_ZW ** 2 * np.eye(3))
            R, w = R @ exp_so3(dx[:3]), w + dx[3:]
        Rf[t], wf[t], Pf[t] = R, w, P
    Rs, ws, Ps = Rf.copy(), wf.copy(), Pf.copy()
    for t in range(n - 2, -1, -1):
        if cut[t + 1]:
            continue
        F, _ = cv_model(ALPHA_REST if rest[t + 1] else ALPHA_MOVE)
        C = Pf[t] @ F.T @ np.linalg.inv(Pp[t + 1])
        e = np.r_[log_so3(Rp[t + 1].T @ Rs[t + 1]), ws[t + 1] - wp[t + 1]]
        dx = C @ e
        Rs[t], ws[t] = Rf[t] @ exp_so3(dx[:3]), wf[t] + dx[3:]
        Ps[t] = Pf[t] + C @ (Ps[t + 1] - Pp[t + 1]) @ C.T
    return Rs, used, resets


def main() -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq
    import trimesh

    here = Path(__file__).resolve().parent
    sys.path[:0] = [str(here), str(here / "gate"), str(here.parents[2] / "libs" / "v2d_infra")]
    from tier_guard import forbid_lower_tiers
    forbid_lower_tiers()  # Tier 3: nothing from Tier 1 or Tier 2 (Kaggle 2.8.c)
    import t3_inputs
    import t3_provenance
    from t3_align_check import similarity
    from t3_dynamics_post import angle, to_q, to_R
    from t3_support import basis
    from t3_symmetry import SYM_M, Shape, nearest_equivalent, symmetries

    root, version, phys, sel, out_v = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3]), Path(sys.argv[4]), sys.argv[5]
    only = {int(x) for x in sys.argv[6].split(",")} if len(sys.argv) > 6 else None
    rn = root / "runs"
    prov = t3_provenance.stamp([root / "input", rn / version, rn / f"{version}_suspect", phys, sel])
    if (rn / out_v).exists() or (rn / f"{out_v}_suspect").exists():
        raise SystemExit(f"runs/{out_v} exists; pick a new name")
    metas = {m["episode_index"]: m for m in map(json.loads, (root / "input/meta/episodes_metadata.jsonl").read_text().splitlines()) if m}
    convert = {r["episode"]: r["convert"] for r in json.loads(sel.read_text())}
    anchors = {r["episode"]: [(a["start"], a["end"]) for a in r["anchors"]]
               for r in json.loads((rn / f"{version}.height_post.json").read_text())}
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
            n_up, d_up, _, _, _ = basis(t3_inputs.ground_plane(root, m))
            low_of = lambda P, RR: (np.einsum("fij,kj->fki", RR, hull) + P[:, None]) @ n_up + d_up

            shape = Shape(mesh, com_b)
            G, sym_axis = symmetries(shape, body.moment_inertia)
            Rc = R.copy()
            if len(G) > 1 or sym_axis is not None:
                for t in range(1, n):
                    Rc[t] = nearest_equivalent(R[t], Rc[t - 1], G, sym_axis)
            for t in range(n):
                if angle(R[t], Rc[t]) > 1e-6 and shape.shift(R[t].T @ Rc[t]) > SYM_M:
                    raise SystemExit(f"{name}: frame {t}'s symmetric turn moves the surface {shape.shift(R[t].T @ Rc[t]):.4f} m")
            com = pos + R @ com_b
            low0 = low_of(pos, Rc).min(1)

            held = np.load(phys / "out" / f"{name}.npz")["held"].astype(bool)
            held = binary_closing(held, np.ones(2 * GAP + 1, bool)) | held
            resting = np.zeros(n, bool)
            for a, b in anchors.get(name, []):
                resting[a:b] = True
            rest = resting & ~held
            _, _, cam, _, _ = similarity(root / "runs" / convert[name] / name)  # world = s r cam + t: the centre is t

            new_com, used_p, resets_p = smooth_position(com, rest, cam)
            new_R, used_r, resets_r = smooth_rotation(Rc, rest)
            dev = np.degrees([angle(new_R[t], Rc[t]) for t in range(n)])
            if (dev[used_r] > GATE_DEG + 1e-6).any():
                t = int(np.flatnonzero(used_r)[np.argmax(dev[used_r])])
                raise SystemExit(f"{name}: frame {t}'s observation was used but the output is {dev[t]:.1f} deg from it")

            new_pos = new_com - new_R @ com_b
            low1 = low_of(new_pos, new_R).min(1)
            lift = np.maximum(0.0, np.minimum(low0, 0.0) - low1)
            new_pos = new_pos + lift[:, None] * n_up
            out = pose.copy()
            out[:, :3], out[:, 3:7] = new_pos, to_q(new_R)
            col = pa.FixedSizeListArray.from_arrays(pa.array(out.astype(np.float32).ravel(), pa.float32()), 7)
            i = table.schema.get_field_index("observation.object.pose")
            out_t = table.set_column(i, table.schema.field(i), col)
            md = dict(out_t.schema.metadata or {})
            md[b"kalman_post"] = json.dumps({"from": version}).encode()
            out_t = out_t.replace_schema_metadata(md)
            dst = rn / dst_v / "data" / "chunk-000" / f.name
            dst.parent.mkdir(parents=True, exist_ok=True)
            pq.write_table(out_t, dst)
            (rn / dst_v / "meta").mkdir(exist_ok=True)
            mf = rn / src_v / "meta" / f"episode_{ep:06d}.metadata.json"
            (rn / dst_v / "meta" / mf.name).write_bytes(mf.read_bytes())

            shift = np.linalg.norm(new_com - com, axis=1)
            row = {"episode": name, "tier": dst_v, "frames": n, "symmetries": len(G), "continuous_axis": sym_axis is not None,
                   "rest_share": round(float(rest.mean()), 3),
                   "position_rejected": int((~used_p).sum()), "position_resets": resets_p,
                   "rotation_rejected": int((~used_r).sum()), "rotation_resets": resets_r,
                   "turn_from_input_deg_p95_max_used": [round(float(np.percentile(dev[used_r], 95)), 1), round(float(dev[used_r].max()), 1)],
                   "turn_from_input_deg_max_rejected": round(float(dev[~used_r].max()), 1) if (~used_r).any() else 0.0,
                   "com_shift_m_p50_p95_max": [round(float(x), 4) for x in np.percentile(shift, [50, 95, 100])],
                   "floor_lifted_frames": int((lift > 0).sum())}
            report.append(row)
            print(json.dumps(row), flush=True)
    (rn / f"{out_v}.kalman_post.json").write_text(json.dumps(report, indent=1))
    t3_provenance.write(rn / f"{out_v}.provenance.json", prov | {"made_by": "t3_kalman_post.py", "from_version": version})


if __name__ == "__main__":
    main()
