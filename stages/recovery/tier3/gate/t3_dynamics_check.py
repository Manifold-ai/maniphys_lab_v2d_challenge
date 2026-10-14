"""Dynamics check on a retargeted robot reference: does the object obey Newton's and Euler's equations for its contact state?

This reads what training consumes (the retargeted g1 parquet), not the human layer. Each frame gets a contact state first,
and only then is the motion judged against what that state allows. Speed never decides the state; one speed threshold
(REST_MPS) separates rest from motion where a rule needs it, with no band in between.

State (per frame):
  held       the reference's own contact label (hand_contact_active, what the reward uses) on either hand, or a palm
             within HOLD_M of the object surface. The union, so an unheld verdict is never caused by a missing label alone.
  supported  not held, and the lowest hull point is within SUPPORT_TOL_M of the floor or of a support top under it.
  airborne   not held and not supported.

Checks (translation of the centre of mass, rotation about it; derivatives by a local quadratic fit over WINDOW_S):
  lin_held          held: |a| <= A_HAND (what a hand can impart).
  lin_airborne      airborne: |a - g| <= A_TOL (free fall).
  lin_supported     supported: vertical |a_z| <= A_TOL; horizontal at rest (|v_h| < REST_MPS) |a_h| <= A_TOL, and when
                    sliding the acceleration must be friction, opposite to v_h with magnitude in [MU_MIN g, MU_MAX g]
                    (within A_TOL). A supported object coasting at constant speed fails here.
  rest_drift        over a contiguous unheld run, the centre of mass moves more than DRIFT_M horizontally from where the
                    run started (nothing pushes it; catches creep slower than any speed threshold).
  rot_torque        |dL/dt| per unit mass within the torque the state allows: unheld, gravity about a contact point
                    (g * r_max); held, a hand (A_HAND * r_max). L = R (I/m) R^T w with I from the mesh, uniform density;
                    w from consecutive frames without smoothing, so a jump is not averaged away.
  rot_drift         over a contiguous unheld run, the centred surface (centre of mass removed) moves more than DRIFT_M
                    (mean nearest-point distance) from its pose at the run start. Shape-aware: turning about a symmetry
                    axis moves no surface and is not motion (Tier 1's bat spins 1.6 rad about its axis untouched).
  rot_jump          one frame turns more than OMEGA_MAX / fps and the centred surface moves at least SYM_M.
  rot_jump_symmetric  the same turn, but the surface moves less than SYM_M: an equivalent pose of a symmetric object.
                    Physically nothing happened, but the orientation target the policy tracks jumped; reported apart
                    and kept out of object_any.
  root_acc          the robot root's |a| <= A_BODY.

Thresholds are physical bounds chosen loose, so a flag means physically impossible rather than unusual. Tier 1 / 2
references are only for reading the false positive rate of the check, never for tuning anything Tier 3 uses.

Usage: t3_dynamics_check.py <motion set dir> <episodes_metadata.jsonl> <support source> <out.json> [episode,...]
  motion set dir   .../runs/motion/<set> (holds whole_body/soma/sequence_id=*/robot_name=g1/data.parquet)
  support source   a directory of <sequence>_support.usda, or "stage" for <motion set dir>/whole_body/reconstructed_stage
"""

import json
import sys
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import trimesh
from scipy.signal import savgol_filter
from scipy.spatial import cKDTree

G = 9.81
WINDOW_S = 0.3
REST_MPS = 0.05
HOLD_M = 0.10
SUPPORT_TOL_M = 0.03
A_TOL = 0.05 * G
A_HAND = 3.0 * G
A_BODY = 2.0 * G
MU_MIN, MU_MAX = 0.2, 1.0
DRIFT_M = 0.03
OMEGA_MAX = 4 * np.pi
SYM_M = 0.01
G_VEC = np.array([0.0, 0.0, -G])


def quat_R(q):
    w, x, y, z = q.T
    return np.stack([np.stack([1-2*(y*y+z*z), 2*(x*y-w*z), 2*(x*z+w*y)], -1),
                     np.stack([2*(x*y+w*z), 1-2*(x*x+z*z), 2*(y*z-w*x)], -1),
                     np.stack([2*(x*z-w*y), 2*(y*z+w*x), 1-2*(x*x+y*y)], -1)], -2)


def supports_of(usda: Path):
    """[(xy_min, xy_max, top_z)] from the support stage's geometry bounds."""
    if not usda.exists():
        return []
    from pxr import Usd, UsdGeom
    stage = Usd.Stage.Open(str(usda))
    cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), [UsdGeom.Tokens.default_])
    out = []
    for prim in stage.Traverse():
        if prim.IsA(UsdGeom.Gprim):
            r = cache.ComputeWorldBound(prim).ComputeAlignedRange()
            lo, hi = np.array(r.GetMin()), np.array(r.GetMax())
            out.append((lo[:2], hi[:2], float(hi[2])))
    return out


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


def check(part: Path, supports):
    cols = ["fps", "robot_root_position", "ee_pose_w", "hand_contact_active", "object_body_position", "object_body_wxyz"]
    r = pq.read_table(part / "data.parquet", columns=cols).to_pylist()[0]
    fps = r["fps"]
    win = int(round(WINDOW_S * fps)) | 1
    sg = lambda x, d: savgol_filter(x, win, 2, deriv=d, delta=1 / fps, axis=0, mode="interp")

    mesh = trimesh.load(part.parent / "object" / "textured_mesh.obj", force="mesh", process=False)
    body = mesh if mesh.is_watertight else mesh.convex_hull
    com_b = np.asarray(body.center_mass)
    I_m = np.asarray(body.moment_inertia) / body.mass  # inertia per unit mass about the centre of mass, body frame
    hull = np.asarray(mesh.convex_hull.vertices)
    r_max = float(np.linalg.norm(hull - com_b, axis=1).max())
    surf = np.asarray(mesh.vertices)
    surf = surf[np.random.default_rng(0).choice(len(surf), min(len(surf), 3000), replace=False)]

    pos = np.array([b[0] for b in r["object_body_position"]])
    q = np.array([b[0] for b in r["object_body_wxyz"]])
    R = quat_R(q)
    n = len(pos)
    com = pos + R @ com_b
    low = np.einsum("tij,vj->tvi", R, hull)[..., 2].min(1) + pos[:, 2]

    palms = np.array(r["ee_pose_w"])[:, :, :3]
    Ws = np.einsum("tij,vj->tvi", R, surf) + pos[:, None]
    palm_d = np.stack([np.linalg.norm(Ws - palms[:, i][:, None], axis=2).min(1) for i in range(palms.shape[1])], 1).min(1)
    label = np.array(r["hand_contact_active"]).max(0) > 0.5
    held = label | (palm_d < HOLD_M)

    gap = np.abs(low)  # the floor is z = 0 in g1_retarget_world
    for lo, hi, top in supports:
        under = np.all((com[:, :2] >= lo) & (com[:, :2] <= hi), axis=1)
        gap = np.where(under, np.minimum(gap, np.abs(low - top)), gap)
    supported = ~held & (gap <= SUPPORT_TOL_M)
    airborne = ~held & ~supported

    v, a = sg(com, 1), sg(com, 2)
    v_h, a_h = v[:, :2], a[:, :2]
    sp_h = np.linalg.norm(v_h, axis=1)
    sliding = sp_h >= REST_MPS
    vhat = v_h / np.maximum(sp_h, 1e-9)[:, None]
    along = -(a_h * vhat).sum(1)  # deceleration along the slide
    across = np.linalg.norm(a_h + along[:, None] * vhat, axis=1)
    fric_excess = np.maximum(0, MU_MIN * G - along) + np.maximum(0, along - MU_MAX * G)
    bad = {
        "lin_held": held & (np.linalg.norm(a, axis=1) > A_HAND),
        "lin_airborne": airborne & (np.linalg.norm(a - G_VEC, axis=1) > A_TOL),
        "lin_supported": supported & ((np.abs(a[:, 2]) > A_TOL)
                                      | (~sliding & (np.linalg.norm(a_h, axis=1) > A_TOL))
                                      | (sliding & (np.hypot(fric_excess, across) > A_TOL))),
    }

    # rotation: raw per-frame angular velocity (a jump must not be smoothed away), Euler's equation per unit mass
    dq = np.einsum("tij,tkj->tik", R[1:], R[:-1])  # R_{t+1} R_t^T
    ang = np.arccos(np.clip((np.trace(dq, axis1=1, axis2=2) - 1) / 2, -1, 1))
    axis = np.stack([dq[:, 2, 1] - dq[:, 1, 2], dq[:, 0, 2] - dq[:, 2, 0], dq[:, 1, 0] - dq[:, 0, 1]], 1)
    axis /= np.maximum(np.linalg.norm(axis, axis=1), 1e-12)[:, None]
    w = np.vstack([axis * ang[:, None] * fps, np.zeros((1, 3))])
    L = np.einsum("tij,jk,tlk,tl->ti", R, I_m, R, w)  # R I R^T w, per unit mass
    tau = np.r_[0.0, np.linalg.norm(np.diff(L, axis=0), axis=1) * fps]
    bad["rot_torque"] = np.where(held, tau > A_HAND * r_max, tau > G * r_max)

    # shape-aware: compare the centred posed surface, so turning about a symmetry axis is no motion
    cen = surf[::6] - com_b
    posed = np.einsum("tij,vj->tvi", R, cen)
    shape_d = lambda a, b: float(cKDTree(posed[a]).query(posed[b])[0].mean())
    step_shape = np.r_[0.0, [shape_d(t, t + 1) if ang[t] > OMEGA_MAX / fps else 0.0 for t in range(n - 1)]]
    jump = np.r_[False, ang > OMEGA_MAX / fps]
    bad["rot_jump"] = jump & (step_shape >= SYM_M)
    bad["rot_jump_symmetric"] = jump & (step_shape < SYM_M)

    drift = np.zeros(n, bool)
    turn = np.zeros(n, bool)
    for s, e in runs(~held):
        drift[s:e] = np.linalg.norm(com[s:e, :2] - com[s, :2], axis=1) > DRIFT_M
        tree = cKDTree(posed[s])
        turn[s:e] = [tree.query(posed[t])[0].mean() > DRIFT_M for t in range(s, e)]
    bad["rest_drift"] = drift
    bad["rot_drift"] = turn

    root = np.array(r["robot_root_position"])
    root_a = np.linalg.norm(sg(root, 2), axis=1)
    bad["root_acc"] = root_a > A_BODY

    obj = np.zeros(n, bool)
    for k in ("lin_held", "lin_airborne", "lin_supported", "rest_drift", "rot_torque", "rot_drift", "rot_jump"):
        obj |= bad[k]
    first = lambda m: int(np.argmax(m)) if m.any() else None
    return {
        "frames": n, "fps": fps, "r_max_m": round(r_max, 4), "watertight": bool(mesh.is_watertight),
        "share": {"held": round(float(held.mean()), 3), "label": round(float(label.mean()), 3),
                  "supported": round(float(supported.mean()), 3), "airborne": round(float(airborne.mean()), 3)},
        "count": {k: int(m.sum()) for k, m in bad.items()},
        "first": {**{k: first(m) for k, m in bad.items()}, "object_any": first(obj)},
        "object_any": int(obj.sum()),
        "measure": {"root_acc_p99_mps2": round(float(np.percentile(root_a, 99)), 2),
                    "tau_unheld_p99": round(float(np.percentile(tau[~held], 99)), 3) if (~held).any() else None,
                    "torque_bound_unheld": round(G * r_max, 3)},
    }


def main():
    mset, meta, sup_src, out = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], Path(sys.argv[4])
    only = {int(x) for x in sys.argv[5].split(",")} if len(sys.argv) > 5 else None
    res = {"set": str(mset), "support": sup_src, "thresholds": {k: v for k, v in globals().items()
           if k.isupper() and isinstance(v, float | int)}, "episodes": {}}
    for m in map(json.loads, open(meta)):
        ep, seq = m["episode_index"], m["sequence_id"]
        if only and ep not in only:
            continue
        part = mset / "whole_body/soma" / f"sequence_id={seq}" / "robot_name=g1"
        if not (part / "data.parquet").exists():
            continue
        sd = mset / "whole_body/reconstructed_stage" if sup_src == "stage" else Path(sup_src)
        res["episodes"][f"ep{ep:02d}"] = {"sequence_id": seq, **check(part, supports_of(sd / f"{seq}_support.usda"))}
        e = res["episodes"][f"ep{ep:02d}"]
        print(f"ep{ep:02d} T={e['frames']:4d} held {e['share']['held']:.2f} sup {e['share']['supported']:.2f} air "
              f"{e['share']['airborne']:.2f} | " + " ".join(f"{k} {v}" for k, v in e["count"].items())
              + f" | 物体首个违规帧 {e['first']['object_any']}", flush=True)
    out.write_text(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
