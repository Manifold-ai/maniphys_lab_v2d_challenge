"""Can the human's hands tell an object's flips apart? Hand-geometry probe for multi-frame orientation flips (10-15).

FoundationPose's scorer could not separate flipped candidates on our objects (1200-2200 px; t3_fp_score_probe.py).
The human is much larger in the image and is reconstructed from Tier 3 input; while an object is held, the hand must
lie on its surface. Per frame, candidates turn the input orientation about the mesh's principal axes through the centre
of mass (STEP_DEG steps); for each hand within HOLD_M of the input pose, the hand surface points (t3_hand_verts_export)
get a signed distance to the candidate's surface (trimesh, positive outside). Energy per candidate: the 10th
percentile of the outside distances (is the hand touching) plus PEN_W times the mean depth inside (is the hand through
the object); lowest wins. Only frames with a hand within HOLD_M are scored.

    python t3_hand_flip_probe.py <tier3 root> <version> <hands dir> <out.json> <ep:frame:truth,...>
truth: "same" (the input orientation is right) or "flip" (the right answer turns the axis of least inertia end over end,
for a body symmetric about that axis, so candidates are compared by where that axis points).
"""

import json
import sys
from pathlib import Path

import numpy as np
import trimesh
from scipy.spatial.transform import Rotation

STEP_DEG = 60
HOLD_M = 0.10
PEN_W = 2.0


def main() -> None:
    root, version, hands_dir, out = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3]), Path(sys.argv[4])
    cases = [c.split(":") for c in sys.argv[5].split(",")]
    metas = {m["episode_index"]: m for m in map(json.loads, (root / "input/meta/episodes_metadata.jsonl").read_text().splitlines()) if m}
    rows = []
    cache = {}
    for ep_s, f_s, truth in cases:
        ep, f = int(ep_s), int(f_s)
        if ep not in cache:
            m = metas[ep]
            mesh = trimesh.load(root / "input" / m["mesh"], force="mesh")
            body = mesh if mesh.is_watertight else mesh.convex_hull
            _, axes = np.linalg.eigh(np.asarray(body.moment_inertia))
            cache[ep] = (mesh, np.asarray(body.center_mass), axes, np.load(hands_dir / f"ep{ep:02d}_hands.npz"))
        mesh, com_b, axes, H = cache[ep]
        pose = H["object_pose"][f].astype(np.float64)
        R = Rotation.from_quat(np.r_[pose[4:7], pose[3]]).as_matrix()
        com = pose[:3] + R @ com_b
        turns = [("none", np.eye(3))] + [(f"ax{k}_{d}", Rotation.from_rotvec(axes[:, k] * np.deg2rad(d)).as_matrix())
                                         for k in range(3) for d in range(STEP_DEG, 360, STEP_DEG)]
        held = []
        for side in ("left", "right"):
            pts = H[side][f].astype(np.float64)
            local = (pts - pose[:3]) @ R
            if np.abs(trimesh.proximity.signed_distance(mesh, local)).min() < HOLD_M:
                held.append(side)
        if not held:
            rows.append({"episode": ep, "frame": f, "truth": truth, "held": []})
            print(json.dumps(rows[-1]), flush=True)
            continue
        pts = np.concatenate([H[s][f] for s in held]).astype(np.float64)
        energy = []
        for _, Rt in turns:
            Rk = R @ Rt
            pk = com - Rk @ com_b
            sd = trimesh.proximity.signed_distance(mesh, (pts - pk) @ Rk)  # trimesh: positive inside
            outside = np.maximum(-sd, 0.0)
            inside = np.maximum(sd, 0.0)
            energy.append(float(np.percentile(outside, 10) + PEN_W * inside.mean()))
        energy = np.asarray(energy)
        order = np.argsort(energy)
        long_axis = axes[:, 0]
        points_same = np.array([float((Rt @ long_axis) @ long_axis) > 0 for _, Rt in turns])  # long axis kept vs flipped
        if truth == "same":
            right = np.array([nm == "none" for nm, _ in turns])
        else:
            right = ~points_same
        best = int(order[0])
        rows.append({"episode": ep, "frame": f, "truth": truth, "held": held, "top": turns[best][0],
                     "top_is_right": bool(right[best]),
                     "best_right_energy_cm": round(float(energy[right].min()) * 100, 2),
                     "best_wrong_energy_cm": round(float(energy[~right].min()) * 100, 2),
                     "input_energy_cm": round(float(energy[0]) * 100, 2)})
        print(json.dumps(rows[-1]), flush=True)
    out.write_text(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()
