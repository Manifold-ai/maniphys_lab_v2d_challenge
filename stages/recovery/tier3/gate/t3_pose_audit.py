"""Pose-change audit: how far each object surface point moved between two versions, frame by frame.

A post-process step changes the object for a reason it states (lock a resting object, spread an offset over a grasp,
lift out of the floor); this measures what it actually did, so a change nobody meant shows up as a number before anyone
trains on it. Per frame: the largest displacement of a surface point between the versions, with the points carried by
each version's pose (correspondence, not nearest-surface distance, which reads a 105 deg turn of a mug as 7 cm), taking
the smallest over the object's true symmetries (t3_symmetry: an equivalent pose is no change). Also the turn angle of
that best match, and how many frames moved more than each of MOVE_M.
Second measure, `visible`: the largest distance from either posed surface to the other (both directions, against the
dense surface sample), i.e. how much the geometry an observer sees changed. It is blind to a turn that maps the shape
onto itself within the sampling floor, so a near-symmetric box flipped 180 deg reads small here and large above; a
mug turning its handle away reads large in both.

When <version> has a dynamics_post record, frames are split into locked (the step meant to change them) and the rest.

    python t3_pose_audit.py <tier3 root> <base version> <version> <out.json> [episode,...]
"""

import json
import sys
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import trimesh
from scipy.spatial.transform import Rotation

sys.path.insert(0, str(Path(__file__).resolve().parent))
from t3_symmetry import Shape, nearest_equivalent, symmetries  # noqa: E402

MOVE_M = (0.02, 0.05, 0.10)
POINTS = 400


def poses(root: Path, version: str, ep: int):
    for sub in ("", "_suspect"):
        f = root / "runs" / (version + sub) / "data/chunk-000" / f"episode_{ep:06d}.parquet"
        if f.exists():
            p = np.stack(pq.read_table(f, columns=["observation.object.pose"]).column(0).to_numpy(zero_copy_only=False)).astype(float)
            return p[:, :3], Rotation.from_quat(np.c_[p[:, 4:7], p[:, 3:4]]).as_matrix()
    return None


def main() -> None:
    root, base, ver, out = Path(sys.argv[1]), sys.argv[2], sys.argv[3], Path(sys.argv[4])
    only = {int(x) for x in sys.argv[5].split(",")} if len(sys.argv) > 5 else None
    metas = {m["episode_index"]: m for m in map(json.loads, (root / "input/meta/episodes_metadata.jsonl").read_text().splitlines()) if m}
    rec_f = root / "runs" / f"{ver}.dynamics_post.json"
    rec = {r["episode"]: r for r in json.loads(rec_f.read_text())} if rec_f.exists() else {}
    rows = []
    for ep, m in sorted(metas.items()):
        if only and ep not in only:
            continue
        a, b = poses(root, base, ep), poses(root, ver, ep)
        if a is None or b is None:
            continue
        name = f"ep{ep:02d}_{m['object']}"
        mesh = trimesh.load(root / "input" / m["mesh"], force="mesh")
        body = mesh if mesh.is_watertight else mesh.convex_hull
        com_b = np.asarray(body.center_mass)
        shape = Shape(mesh, com_b)
        G, axis = symmetries(shape, body.moment_inertia)
        pts = trimesh.sample.sample_surface(mesh, POINTS, seed=2)[0] - com_b
        n = min(len(a[0]), len(b[0]))
        disp, turn, vis = np.zeros(n), np.zeros(n), np.zeros(n)
        q = shape.query[::5]
        for t in range(n):
            Ra, Rb = a[1][t], b[1][t]
            Rb_eq = nearest_equivalent(Rb, Ra, G, axis) if (len(G) > 1 or axis is not None) else Rb
            ca, cb = a[0][t] + Ra @ com_b, b[0][t] + Rb @ com_b
            disp[t] = np.linalg.norm(pts @ Rb_eq.T + cb - (pts @ Ra.T + ca), axis=1).max()
            ab = (q @ Rb.T + cb - ca) @ Ra  # b's surface in a's centred body frame
            ba = (q @ Ra.T + ca - cb) @ Rb
            vis[t] = max(shape.tree.query(ab)[0].max(), shape.tree.query(ba)[0].max())
            turn[t] = np.degrees(np.arccos(np.clip((np.trace(Ra.T @ Rb_eq) - 1) / 2, -1, 1)))
        locked = np.zeros(n, bool)
        for r in rec.get(name, {}).get("locked_runs", []):
            locked[r["start"]:r["end"]] = True
        row = {"episode": name, "frames": n, "symmetries": len(G), "continuous_axis": axis is not None,
               "disp_m_p50_p95_max": [round(float(x), 4) for x in np.percentile(disp, [50, 95, 100])],
               "turn_deg_p95_max": [round(float(x), 1) for x in np.percentile(turn, [95, 100])],
               "worst_frame": int(np.argmax(disp)),
               "visible_m_p50_p95_max": [round(float(x), 4) for x in np.percentile(vis, [50, 95, 100])],
               "visible_worst_frame": int(np.argmax(vis))}
        for mv in MOVE_M:
            row[f"frames_over_{int(mv * 100)}cm"] = int((disp > mv).sum())
            row[f"visible_frames_over_{int(mv * 100)}cm"] = int((vis > mv).sum())
            if rec:
                row[f"frames_over_{int(mv * 100)}cm_outside_locked"] = int(((disp > mv) & ~locked).sum())
                row[f"visible_frames_over_{int(mv * 100)}cm_outside_locked"] = int(((vis > mv) & ~locked).sum())
        rows.append(row)
        print(json.dumps(row), flush=True)
    out.write_text(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()
