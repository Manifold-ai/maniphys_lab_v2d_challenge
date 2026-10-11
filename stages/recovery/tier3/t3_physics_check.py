"""Physical plausibility of the assembled Tier 3 data, on what the downstream reads (the parquet), Tier 3 inputs only.

The ideas come from mono's gate 2 (services/sim_worker qc/checks.py), but there is no engine here: no contact events,
no impulses, no recorded velocities. Each gate-2 law is replaced by the kinematic statement it implies for a
reconstructed trajectory, in the released world frame, with the released ground plane (n.x + d = 0, n up) and the
official mesh:

  object_floor_penetration   (SIM-C165, penetration of a static body) the mesh's lowest point is more than FLOOR_TOL_M
                             below the floor.
  unheld_motion              (SIM-C178, contacts push only where they touch) the object moves faster than MOVE_MPS
                             while no hand joint is within HOLD_M of its surface, and it is not falling: its vertical
                             acceleration is not within FALL_TOL of gravity.
  rest_drift / rest_jitter   (SIM-C026, a resting body stays put) over a rest segment (slower than REST_MPS, not held,
                             at least MIN_SEGMENT frames) the object drifts more than DRIFT_M end to end, or its
                             position scatters more than JITTER_M RMS about the segment median.
  pose_jump                  (SIM-C104, motion must be self-consistent) the object moves more than JUMP_M between two
                             consecutive frames (raw poses, 3 m/s at 30 fps), as t3_track_check.py.
  acceleration_spike         the object's smoothed acceleration exceeds ACC_MAX: no hand moves a held object that fast.
                             Smoothing spreads a one-frame jump over several frames, so jumps are pose_jump's job.
  feet_penetration / feet_floating
                             the lower sole point of the two feet is more than FLOOR_TOL_M below the floor, or more
                             than FEET_FLOAT_M above it (no task here has both feet off the ground). This one does not
                             share data with the floor correction (t3_floor_fit.py fits object contact events), so it is
                             an independent check of the world frame.
  rest_off_floor             reported, not judged: rest segments whose lowest point is above the floor by more than
                             FLOOR_TOL_M. They are on a support or floating; telling which needs the support geometry,
                             which Tier 3 does not give (support_surface is not used, see the handoff).

Thresholds come from these definitions and from the world frame's measured accuracy (floor acceptance: resting objects
1.09 cm median, 3.86 cm max off the released plane), not from fitting any reference. Each finding names what was read,
what was expected and what was found, so a red flag can be attributed: data error, a premise that does not hold (e.g. an
object resting on a table counted as off floor), or a bug here.

Two steps, because the parquet reader and SOMA live in different environments:
    host venv:  python t3_physics_check.py extract <tier3 root> <tier dir> <npz dir>
    v2d_cari4d: python t3_physics_check.py check   <tier3 root> <npz dir> <soma assets> <out dir>
"""

from __future__ import annotations

import json
import t3_inputs  # noqa: E402  (same directory: released inputs Tier 3 may read)
import sys
from pathlib import Path

import numpy as np

FPS = 30.0
G = 9.81
FLOOR_TOL_M = 0.03
FEET_FLOAT_M = 0.05
HOLD_M = 0.10
MOVE_MPS = 0.15
REST_MPS = 0.05
FALL_TOL = 0.5 * G
DRIFT_M = 0.03
JITTER_M = 0.01
ACC_MAX = 30.0
JUMP_M = 0.10
SMOOTH = 5
MIN_SEGMENT = 8
HUMAN_COLUMNS = {"poses": "observation.human.pose", "transl": "observation.human.translation",
                 "identity_coeffs": "observation.human.identity_coeffs", "scale_params": "observation.human.scale_params",
                 "bone_length_flexibles": "observation.human.bone_length_flexibles"}


def extract(root: Path, tier: Path, out: Path) -> None:
    import pyarrow.parquet as pq

    out.mkdir(parents=True, exist_ok=True)
    for path in sorted((tier / "data/chunk-000").glob("episode_*.parquet")):
        t = pq.read_table(path)
        col = lambda c: np.stack(t.column(c).to_numpy(zero_copy_only=False)).astype(np.float64)
        arrays = {k: col(c) for k, c in HUMAN_COLUMNS.items()}
        arrays["object_pose"] = col("observation.object.pose")
        arrays["frame_index"] = t.column("frame_index").to_numpy()
        arrays["episode_index"] = int(t.column("episode_index")[0].as_py())
        np.savez(out / f"{path.stem}.npz", tier=tier.name, **arrays)
        print(path.stem, t.num_rows)


def runs(mask: np.ndarray) -> list[tuple[int, int]]:
    edges = np.flatnonzero(np.diff(np.r_[0, mask.astype(int), 0]))
    return [(int(a), int(b)) for a, b in zip(edges[::2], edges[1::2])]


def segments(mask: np.ndarray, min_len: int = MIN_SEGMENT) -> list[tuple[int, int]]:
    return [(a, b) for a, b in runs(mask) if b - a >= min_len]


def check(root: Path, npz_dir: Path, assets: str, out: Path) -> None:
    import trimesh
    from scipy.ndimage import uniform_filter1d
    from scipy.spatial import cKDTree
    from scipy.spatial.transform import Rotation
    from soma import SOMALayer
    from soma.units import Unit

    from t3_world_probe import soma_cv

    layer = SOMALayer(data_root=assets, identity_model_type="mhr", device="cpu", output_unit=Unit.METERS,
                      enable_procedural_transforms=False)
    names = [str(x) for x in layer._public_joint_names]
    hand_idx = [i for i, nm in enumerate(names) if "Hand" in nm]
    w = np.asarray(layer.skinning_weights, np.float64)
    soles = [np.nonzero(w[:, [names.index(f"{s}Foot"), names.index(f"{s}ToeBase"), names.index(f"{s}ToeEnd")]].sum(1) >= 0.5)[0]
             for s in ("Left", "Right")]
    metas = {m["episode_index"]: m for m in map(json.loads, (root / "input/meta/episodes_metadata.jsonl").read_text().splitlines()) if m}
    out.mkdir(parents=True, exist_ok=True)
    summary = []
    for f in sorted(npz_dir.glob("episode_*.npz")):
        z = np.load(f)
        ep = int(z["episode_index"])
        m = metas[ep]
        name = f"ep{ep:02d}_{m['object']}"
        gp = np.asarray(t3_inputs.ground_plane(root, m), np.float64)
        up, d = gp[:3] / np.linalg.norm(gp[:3]), gp[3] / np.linalg.norm(gp[:3])
        if d < 0:  # the camera (origin) is above the floor: n points up
            up, d = -up, -d
        height = lambda p: p @ up + d

        mesh = trimesh.load(root / "input" / m["mesh"], force="mesh")
        hull = np.asarray(mesh.convex_hull.vertices, np.float64)
        surface = np.asarray(trimesh.sample.sample_surface_even(mesh, 20000, seed=0)[0], np.float64)
        pose = z["object_pose"]
        n = len(pose)
        rot = Rotation.from_quat(np.c_[pose[:, 4:7], pose[:, 3:4]]).as_matrix()
        pos = pose[:, :3]
        obj_low = height(np.einsum("fij,kj->fki", rot, hull) + pos[:, None]).min(1)

        joints, verts = soma_cv({k: z[k] for k in HUMAN_COLUMNS}, layer)
        hands = joints[:, hand_idx]
        local = np.einsum("nji,nhj->nhi", rot, hands - pos[:, None])  # R^T (p - t)
        hand_d = cKDTree(surface).query(local.reshape(-1, 3))[0].reshape(n, -1).min(1)
        held = hand_d < HOLD_M
        sole_low = np.stack([height(verts[:, idx]).min(1) for idx in soles], 1)  # (n, 2)
        feet = sole_low.min(1)

        ps = uniform_filter1d(pos, SMOOTH, axis=0, mode="nearest")
        vel = np.gradient(ps, axis=0) * FPS
        acc = np.gradient(uniform_filter1d(vel, SMOOTH, axis=0, mode="nearest"), axis=0) * FPS
        speed = np.linalg.norm(vel, axis=1)
        acc_n = np.linalg.norm(acc, axis=1)
        acc_up = acc @ up

        findings = []

        def add(check_name: str, mask: np.ndarray, read: str, expect: str, measure, min_len: int = MIN_SEGMENT):
            segs = segments(mask, min_len)
            if segs:
                findings.append({"check": check_name, "frames": int(sum(b - a for a, b in segs)), "read": read, "expect": expect,
                                 "segments": [{"start": a, "end": b, **measure(a, b)} for a, b in segs]})

        r4 = lambda x: round(float(x), 4)
        add("object_floor_penetration", obj_low < -FLOOR_TOL_M, "lowest hull point above the released plane",
            f">= -{FLOOR_TOL_M} m", lambda a, b: {"min_m": r4(obj_low[a:b].min()), "median_m": r4(np.median(obj_low[a:b]))}, 1)
        falling = np.abs(acc_up + G) < FALL_TOL
        add("unheld_motion", (speed > MOVE_MPS) & ~held & ~falling, "object speed, nearest hand joint to the surface, vertical acceleration",
            f"moving (> {MOVE_MPS} m/s) only with a hand within {HOLD_M} m, or in free fall",
            lambda a, b: {"speed_median_mps": r4(np.median(speed[a:b])), "hand_d_median_m": r4(np.median(hand_d[a:b])),
                          "acc_up_median_mps2": r4(np.median(acc_up[a:b]))})
        step = np.r_[0.0, np.linalg.norm(np.diff(pos, axis=0), axis=1)]
        add("pose_jump", step > JUMP_M, "object displacement between consecutive frames (raw)", f"<= {JUMP_M} m",
            lambda a, b: {"max_m": r4(step[a:b].max())}, 1)
        add("acceleration_spike", acc_n > ACC_MAX, "object acceleration (smoothed)", f"<= {ACC_MAX} m/s^2",
            lambda a, b: {"max_mps2": r4(acc_n[a:b].max()), "held_share": r4(held[a:b].mean())}, 1)
        add("feet_penetration", feet < -FLOOR_TOL_M, "lower sole point of the two feet above the released plane",
            f">= -{FLOOR_TOL_M} m", lambda a, b: {"min_m": r4(feet[a:b].min()), "median_m": r4(np.median(feet[a:b]))})
        add("feet_floating", feet > FEET_FLOAT_M, "lower sole point of the two feet above the released plane",
            f"<= {FEET_FLOAT_M} m (one foot on the ground)", lambda a, b: {"median_m": r4(np.median(feet[a:b]))})

        rest = (speed < REST_MPS) & ~held
        rest_rows = []
        for a, b in segments(rest):
            p = pos[a:b]
            drift = float(np.linalg.norm(p[-1] - p[0]))
            jitter = float(np.sqrt(((p - np.median(p, 0)) ** 2).sum(1).mean()))
            low = float(np.median(obj_low[a:b]))
            rest_rows.append({"start": a, "end": b, "drift_m": r4(drift), "jitter_rms_m": r4(jitter), "lowest_median_m": r4(low),
                              "on": "floor" if abs(low) <= FLOOR_TOL_M else ("below_floor" if low < 0 else "off_floor")})
        for key, lim, label in (("drift_m", DRIFT_M, "rest_drift"), ("jitter_rms_m", JITTER_M, "rest_jitter")):
            bad = [r for r in rest_rows if r[key] > lim]
            if bad:
                findings.append({"check": label, "frames": sum(r["end"] - r["start"] for r in bad),
                                 "read": f"object position over a rest segment ({key})", "expect": f"<= {lim} m", "segments": bad})

        report = {"episode": name, "tier": str(z["tier"]), "frames": n,
                  "thresholds": {k: v for k, v in globals().items() if k.isupper() and isinstance(v, float | int) and k not in ("FPS",)},
                  "measurements": {"object_lowest_m_p5_p50_p95": np.percentile(obj_low, [5, 50, 95]).round(4).tolist(),
                                   "feet_lowest_m_p5_p50_p95": np.percentile(feet, [5, 50, 95]).round(4).tolist(),
                                   "held_share": r4(held.mean()), "moving_share": r4((speed > MOVE_MPS).mean()),
                                   "rest_segments": rest_rows},
                  "findings": findings}
        (out / f"{name}.json").write_text(json.dumps(report, indent=1))
        np.savez_compressed(out / f"{name}.npz", obj_low=obj_low, feet=feet, sole_low=sole_low, hand_d=hand_d, speed=speed,
                            acc=acc, held=held)
        row = {"episode": name, "tier": report["tier"], **{fd["check"]: fd["frames"] for fd in findings},
               "feet_p50": report["measurements"]["feet_lowest_m_p5_p50_p95"][1],
               "obj_low_p50": report["measurements"]["object_lowest_m_p5_p50_p95"][1],
               "rest_off_floor": sum(1 for r in rest_rows if r["on"] == "off_floor")}
        summary.append(row)
        print(json.dumps(row), flush=True)
    (out / "summary.json").write_text(json.dumps(summary, indent=1))


def main() -> None:
    cmd = sys.argv[1]
    if cmd == "extract":
        extract(Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]))
    elif cmd == "check":
        check(Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4], Path(sys.argv[5]))
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
