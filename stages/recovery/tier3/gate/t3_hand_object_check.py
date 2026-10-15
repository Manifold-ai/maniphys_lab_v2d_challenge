"""Hand-object consistency of a retargeted reference: is the robot hand on the object when the reference says it is?

The training reference pairs the robot's motion with the object's and with a per-hand contact label
(`hand_contact_active`). Post-processes that move the object (locking, offsets, height shifts) leave the body where it
was, so every one of them can pull the object out of the hand or push it through the fingers; no other check measures
this (t3_dynamics_check only uses a 10 cm hand distance to decide whether the object is touched). Per hand and frame,
from forward kinematics of the training URDF (t3_dynamics_check.limb_points, split by link):

  dist      the smallest distance from the hand's link collision points (palm and fingers) to the object surface
            (SURF points sampled on the mesh, posed by the reference).
  inside    the deepest a hand point lies inside the object (0 when outside; depth to the nearest of 20000 points
            sampled on its surface). The mesh itself when it is watertight ("inside_test": "mesh"); otherwise its convex
            hull ("hull"), which fills concave
            parts (a mug's handle, a basket), so this over-reads on those objects.

Reported per episode and hand: labelled frames; among them dist p50 / p95 and the frames farther than AWAY_M ("label on,
hand away"); unlabelled frames closer than TOUCH_M ("touching, no label"); labelled frames deeper than DEEP_M inside the
hull. Plus the retarget's own `ik_error_per_frame` p95 / max, which says how far the robot is from its IK targets.

    T3_GATE=<gate dir> python t3_hand_object_check.py <motion set dir> <episodes_metadata.jsonl> <out.json> [episode,...]
"""

import json
import re
import sys
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import trimesh
from scipy.spatial import Delaunay, cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parent))  # run with -I
from t3_dynamics_check import limb_points, quat_R  # noqa: E402

SURF = 3000
AWAY_M = 0.03
TOUCH_M = 0.01
DEEP_M = 0.01


def main() -> None:
    mset, meta, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    only = {int(x) for x in sys.argv[4].split(",")} if len(sys.argv) > 4 else None
    rows = []
    for m in map(json.loads, open(meta)):
        ep, seq = m["episode_index"], m["sequence_id"]
        if only and ep not in only:
            continue
        part = mset / "whole_body/soma" / f"sequence_id={seq}" / "robot_name=g1"
        if not (part / "data.parquet").exists():
            continue
        r = pq.read_table(part / "data.parquet").to_pylist()[0]
        sides = list(r["hand_sides"])
        if sorted(sides) != ["left", "right"]:
            raise SystemExit(f"ep{ep:02d}: unexpected hand_sides {sides}")
        label = np.asarray(r["hand_contact_active"], np.float64) > 0.5  # (2, T), in hand_sides order
        mesh = trimesh.load(part.parent / "object" / "textured_mesh.obj", force="mesh", process=False)
        surf = trimesh.sample.sample_surface(mesh, SURF, seed=0)[0]
        hull = mesh.convex_hull
        surf_tree = cKDTree(surf)  # body frame: hand points are carried into it, so one tree serves every frame
        hull_in = Delaunay(np.asarray(hull.vertices))
        solid = mesh if mesh.is_watertight else hull  # the mesh itself when closed; else the hull, which over-reads
        solid_tree = cKDTree(trimesh.sample.sample_surface(solid, 20000, seed=1)[0])
        pos = np.array([b[0] for b in r["object_body_position"]])
        R = quat_R(np.array([b[0] for b in r["object_body_wxyz"]]))
        links = limb_points(r, feet=False, split=True)
        T = len(pos)
        row = {"episode": f"ep{ep:02d}_{m['object']}", "frames": T, "inside_test": "mesh" if solid is mesh else "hull"}
        for h, side in enumerate(sides):
            pts = np.concatenate([P for nm, P in links.items() if re.match(rf"{side}_hand_", nm)], axis=1)  # (T, K, 3)
            local = np.einsum("tkd,tdj->tkj", pts - pos[:, None], R)  # hand points in the object's body frame
            flat = local.reshape(-1, 3)
            dist = surf_tree.query(flat)[0].reshape(T, -1).min(1)
            inside = hull_in.find_simplex(flat) >= 0
            if inside.any() and solid is mesh:
                idx = np.flatnonzero(inside)
                inside[idx] = mesh.contains(flat[idx])
            d_in = np.zeros(len(flat))
            if inside.any():
                d_in[inside] = solid_tree.query(flat[inside])[0]
            depth = d_in.reshape(T, -1).max(1)
            lab = label[h]
            row[side] = {
                "labelled": int(lab.sum()),
                "dist_m_p50_p95_labelled": [round(float(np.percentile(dist[lab], q)), 4) for q in (50, 95)] if lab.any() else None,
                "label_on_hand_away": int((lab & (dist > AWAY_M)).sum()),
                "touching_no_label": int((~lab & (dist < TOUCH_M)).sum()),
                "labelled_deep_inside_hull": int((lab & (depth > DEEP_M)).sum()),
                "depth_m_max_labelled": round(float(depth[lab].max()), 4) if lab.any() else 0.0,
            }
        ik = np.asarray(r["ik_error_per_frame"], np.float64)
        row["ik_error_p95_max"] = [round(float(np.percentile(ik, 95)), 4), round(float(ik.max()), 4)]
        rows.append(row)
        print(json.dumps(row), flush=True)
    out.write_text(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()
