"""Depth errors of the hand and of the object, on frames where a held object rests on the floor (diagnosis, CPU).

Held frames have no surface to fix the object's depth, so its depth there must come from the hand, from its own
reconstruction, or from both weighted by how wrong each is. This measures both on the frames where a third, independent
reference exists: the object rests on the floor (a static segment whose median lowest hull point is within FLOOR_TOL_M,
t3_support's rule) while a hand holds it (physics check: a contact joint within HOLD_M). The floor is the released plane,
not derived from the episode's objects; our supports are (their height is the objects'), so they are not used here.
Caveat: the camera group's floor fit used objects resting on the floor across episodes, so an error common to a group is
absorbed and not seen; and floor rests are picked within FLOOR_TOL_M, so the object's error is underestimated.

Per frame, scaling the object about the camera centre (every point along its own ray, the image unchanged):
  k_floor   the scale that puts its lowest hull point on the floor: the object's depth error is k_floor - 1;
  hand set  the scales at which some hand joint is within TOUCH_M of the object's surface: what the hand allows. Not one
            scale: where the hand overlaps the object in the image, the object's near and far sides both reach it at
            some scale (10-13: taking the scale of closest approach read 12-15 cm of hand error that was this ambiguity).
            Also the set minus scales where a hand joint sits more than INSIDE_M inside the object's convex hull (a hull
            overstates concave objects, a basket's handle or a stool's frame, so this one is indicative).
Reported: the set's width in cm at the object's distance (how much depth the hand pins down), whether k_floor is in it
(whether the hand agrees with the floor), and the distance from k_floor to the set's nearest scale.

Runs in the v2d_cari4d image (soma, trimesh, scipy), CPU, as t3_physics_check.py check:
    python t3_hand_depth_diag.py <tier3 root> <physics dir> <selection json> <soma assets> <out json> [ep=convert dir ...]
"""

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import t3_inputs  # noqa: E402
from t3_support import FLOOR_TOL_M, basis, static_segments  # noqa: E402
from t3_world_probe import soma_cv, soma_joint_names  # noqa: E402

HUMAN = ("poses", "transl", "identity_coeffs", "scale_params", "bone_length_flexibles")
K_GRID = np.arange(0.80, 1.20001, 0.0025)
TOUCH_M = 0.03
INSIDE_M = 0.02
SURFACE_POINTS = 3000
STRIDE = 2


def camera_centre(conv: Path) -> np.ndarray:
    c = np.load(conv / "object_cam_focal.npz")["T_cam_glb"][:, :3, 3]
    w = np.load(conv / "object_world.npz")["T_world_glb"][:, :3, 3]
    mc, mw = c.mean(0), w.mean(0)
    u, sv, vt = np.linalg.svd((w - mw).T @ (c - mc))
    dd = np.diag([1, 1, np.sign(np.linalg.det(u @ vt))])
    r = u @ dd @ vt
    s = np.trace(np.diag(sv) @ dd) / ((c - mc) ** 2).sum()
    return mw - s * r @ mc


def hand_sets(surf: np.ndarray, eqs: np.ndarray, hands: np.ndarray, cam: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Per K_GRID scale: some hand joint within TOUCH_M of the scaled surface; and no joint deeper than INSIDE_M in the hull."""
    from scipy.spatial import cKDTree
    tree = cKDTree(hands)
    touch, clear = np.zeros(len(K_GRID), bool), np.zeros(len(K_GRID), bool)
    for i, k in enumerate(K_GRID):
        touch[i] = tree.query(cam + k * (surf - cam))[0].min() <= TOUCH_M
        local = cam + (hands - cam) / k                       # the hand in the unscaled object's frame of scale
        depth_in = -(local @ eqs[:, :3].T + eqs[:, 3]).max(1) * k  # >0 inside the scaled hull, metres
        clear[i] = (depth_in <= INSIDE_M).all()
    return touch, touch & clear


def main() -> None:
    import trimesh
    from scipy.spatial.transform import Rotation
    from soma import SOMALayer
    from soma.units import Unit

    root, phys, sel, assets, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4], Path(sys.argv[5])
    over = dict(x.split("=", 1) for x in sys.argv[6:])
    metas = {m["episode_index"]: m for m in map(json.loads, (root / "input/meta/episodes_metadata.jsonl").read_text().splitlines()) if m}
    layer = SOMALayer(data_root=assets, identity_model_type="mhr", device="cpu", output_unit=Unit.METERS, enable_procedural_transforms=False)
    rows, pool_o, pool_h = [], [], []
    only = {int(x) for x in __import__("os").environ.get("EPS", "").split(",") if x}
    for r in json.loads(sel.read_text()):
        ep, name = r["episode_index"], r["episode"]
        if only and ep not in only:
            continue
        m = metas[ep]
        z = np.load(phys / "npz" / f"episode_{ep:06d}.npz")
        o = np.load(phys / "out" / f"{name}.npz")
        held = o["held"].astype(bool)
        pose = z["object_pose"]
        pos = pose[:, :3]
        lowp = o["obj_low"]
        rest = np.zeros(len(pos), bool)
        for a, b in static_segments(pos):
            if np.median(lowp[a:b]) <= FLOOR_TOL_M:
                rest[a:b] = True
        frames = np.flatnonzero(rest & held)[::STRIDE]
        if len(frames) < 5:
            rows.append({"episode": name, "frames": int(len(frames))})
            print(json.dumps(rows[-1]), flush=True)
            continue
        cam = camera_centre(root / "runs" / over.get(name, r["convert"]) / name)
        n, d, _, _, _ = basis(t3_inputs.ground_plane(root, m))
        mesh = trimesh.load(root / "input" / m["mesh"], force="mesh")
        hull = np.asarray(mesh.convex_hull.vertices, np.float64)
        from scipy.spatial import ConvexHull
        eqs_local = ConvexHull(hull).equations  # n.x + d <= 0 inside, object frame
        surf = np.asarray(trimesh.sample.sample_surface_even(mesh, SURFACE_POINTS, seed=0)[0], np.float64)
        joints, _ = soma_cv({k: z[k][frames] for k in HUMAN}, layer)
        names = soma_joint_names(layer, joints.shape[1])
        hand = [i for i, nm in enumerate(names) if "Hand" in nm]
        rot = Rotation.from_quat(np.c_[pose[frames, 4:7], pose[frames, 3:4]]).as_matrix()
        hc = cam @ n + d
        e_o, depth, res = [], [], {"touch": [], "clear": []}
        for j, f in enumerate(frames):
            hv = hull @ rot[j].T + pos[f]
            k_floor = -hc / ((hv - cam) @ n).min()
            dist = float(np.linalg.norm(pos[f] - cam))
            eqs = np.c_[eqs_local[:, :3] @ rot[j].T, eqs_local[:, 3] - (eqs_local[:, :3] @ rot[j].T) @ pos[f]]
            sets = dict(zip(("touch", "clear"), hand_sets(surf @ rot[j].T + pos[f], eqs, joints[j, hand], cam)))
            for key, ok in sets.items():
                ks = K_GRID[ok]
                res[key].append((len(ks) * 0.0025 * dist * 100,
                                 bool(len(ks)) and float(np.abs(ks - k_floor).min()) <= 0.0025,
                                 float(np.abs(ks - k_floor).min()) * dist * 100 if len(ks) else np.nan))
            e_o.append((k_floor - 1) * dist)
            depth.append(dist)
        e_o = np.array(e_o) * 100
        pool_o += e_o.tolist()
        q = lambda x: [round(float(v), 2) for v in np.nanpercentile(x, [10, 50, 90])]
        row = {"episode": name, "frames": int(len(frames)), "depth_m_p50": round(float(np.median(depth)), 2),
               "object_depth_err_cm_p10_p50_p90": q(e_o), "object_depth_err_cm_std": round(float(np.std(e_o)), 2)}
        for key, v in res.items():
            w, inside, off = (np.array(x, float) for x in zip(*v))
            row[f"hand_{key}"] = {"width_cm_p10_p50_p90": q(w), "empty_share": round(float((w == 0).mean()), 3),
                                  "floor_in_share": round(float(inside.mean()), 3), "floor_off_cm_p50_p90": q(off)[1:]}
            pool_h.append(row[f"hand_{key}"])
        rows.append(row)
        print(json.dumps(row), flush=True)
    po = np.array(pool_o)
    ok = [x for x in rows if "hand_touch" in x]
    summary = {"frames": int(len(po)), "episodes": len(ok),
               "object_depth_err_cm_p10_p50_p90": [round(float(v), 2) for v in np.percentile(po, [10, 50, 90])],
               "object_rms_cm": round(float(np.sqrt((po ** 2).mean())), 2)}
    for key in ("touch", "clear"):
        summary[f"hand_{key}_width_cm_episode_medians_p50"] = round(float(np.median([x[f"hand_{key}"]["width_cm_p10_p50_p90"][1] for x in ok])), 2)
        summary[f"hand_{key}_floor_in_share_episode_median"] = round(float(np.median([x[f"hand_{key}"]["floor_in_share"] for x in ok])), 3)
    print(json.dumps(summary))
    out.write_text(json.dumps({"summary": summary, "episodes": rows}, indent=1))


if __name__ == "__main__":
    main()
