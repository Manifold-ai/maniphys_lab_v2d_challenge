"""Where does the Tier 3 object error left after world calibration come from? Evaluation only; the references read here
never feed the Tier 3 data.

Calibration: one similarity world <- camera per episode, fitted on all frames of our human joints against the released
Tier 2 human (as in t3_world_probe.py, variant human_fit_reference); the object never enters the fit. Object position
error e_t = ours_t - ref_t against rxzhou's Tier 2 v5.4 denoised poses, split as
  - offset: the episode mean of e_t (constant part), also split into vertical (along the released floor normal) and
    along the camera ray (monocular depth direction);
  - drift:  e_t - offset smoothed over SMOOTH_S (slow part);
  - jitter: what is left (fast part).
Frames are also split by the reference's own motion into static (object at rest) and moving, and on static frames the
height of the object's lowest point above the released ground plane is compared, ours vs reference.

    python t3_world_eval.py <tier3 root> <dir with tier2 episode_*.npz> <tier2_v54 dir> <soma assets> <out .json>
"""

import json
import sys
from pathlib import Path

import numpy as np
import trimesh
from scipy.ndimage import uniform_filter1d
from scipy.spatial.transform import Rotation

from t3_world_probe import HUMAN_KEYS, plane_up, rot_deg, soma_cv, umeyama

FPS = 30.0
SMOOTH_S = 0.5
STATIC_MPS = 0.03  # reference object slower than this ...
STATIC_DPS = 10.0  # ... and turning slower than this: at rest
STATIC_MIN = 15  # frames


def runs(mask: np.ndarray) -> list[tuple[int, int]]:
    edges = np.flatnonzero(np.diff(np.r_[0, mask.astype(int), 0]))
    return [(a, b) for a, b in zip(edges[::2], edges[1::2])]


def cm(x: np.ndarray) -> float | None:
    return round(float(x) * 100, 1) if np.size(x) and np.isfinite(x) else None


def p50(x: np.ndarray) -> float | None:
    return cm(np.median(x)) if len(x) else None


def main() -> None:
    from soma import SOMALayer
    from soma.units import Unit

    root, t2dir, v54, assets, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4], Path(sys.argv[5])
    layer = SOMALayer(data_root=assets, identity_model_type="mhr", device="cpu", output_unit=Unit.METERS,
                      enable_procedural_transforms=False)
    metas = [json.loads(line) for line in (root / "input/meta/episodes_metadata.jsonl").read_text().splitlines() if line.strip()]
    rows = []
    for m in metas:
        ep = m["episode_index"]
        name = f"ep{ep:02d}_{m['object']}"
        conv = root / "runs/convert" / name
        if not (conv / "soma_params.npz").exists():
            rows.append({"episode": name, "skipped": "no reconstruction"})
            print(json.dumps(rows[-1]), flush=True)
            continue
        ours = dict(np.load(conv / "soma_params.npz", allow_pickle=True))
        t2 = dict(np.load(t2dir / f"episode_{ep:06d}.npz"))
        ref = np.load(v54 / f"episode_{ep:06d}.npz", allow_pickle=True)
        cam = np.load(conv / "object_cam.npz")["T_cam_glb"]
        n = min(len(ours["poses"]), len(t2["poses"]), len(cam), len(ref["object_pose"]))
        ja, _ = soma_cv({k: ours[k][:n] for k in HUMAN_KEYS}, layer)
        jb, _ = soma_cv({k: t2[k][:n] for k in HUMAN_KEYS}, layer)
        s, r, t = umeyama(ja.reshape(-1, 3), jb.reshape(-1, 3))
        gp = json.loads((root / "input" / m["ground_plane"]).read_text())["plane"]
        n_w, d_w = plane_up(np.asarray(gp[:3], np.float64), float(gp[3]))

        vis = ref["visible"][:n].astype(bool)
        q = ref["object_pose"][:n]
        rt = q[:, :3]
        rr = np.tile(np.eye(3), (n, 1, 1))
        rr[vis] = Rotation.from_quat(np.c_[q[vis, 4:7], q[vis, 3:4]]).as_matrix()
        ot = s * cam[:n, :3, 3] @ r.T + t
        orr = np.einsum("ij,njk->nik", r, cam[:n, :3, :3])

        # static / moving from the reference's own motion (evaluation only), on visible runs
        speed = np.full(n, np.inf)
        turn = np.full(n, np.inf)
        for a, b in runs(vis):
            if b - a < 3:
                continue
            sm = uniform_filter1d(rt[a:b], 5, axis=0, mode="nearest")
            speed[a:b] = np.linalg.norm(np.gradient(sm, axis=0), axis=1) * FPS
            rv = Rotation.from_matrix(rr[a:b])
            dth = np.r_[0.0, np.degrees(np.linalg.norm((rv[1:] * rv[:-1].inv()).as_rotvec(), axis=1))]
            turn[a:b] = uniform_filter1d(dth, 5, mode="nearest") * FPS
        still = vis & (speed < STATIC_MPS) & (turn < STATIC_DPS)
        static = np.zeros(n, bool)
        for a, b in runs(still):
            if b - a >= STATIC_MIN:
                static[a:b] = True
        moving = vis & ~static

        e = ot - rt
        off = e[vis].mean(0)
        res = np.zeros_like(e)
        drift = np.zeros_like(e)
        res[vis] = e[vis] - off
        for a, b in runs(vis):
            drift[a:b] = uniform_filter1d(res[a:b], max(1, int(SMOOTH_S * FPS)), axis=0, mode="nearest")
        jit = res - drift
        ray = ot[vis] - t  # camera centre in the world is t
        ray /= np.linalg.norm(ray, axis=1, keepdims=True)
        ray_m = ray.mean(0)
        ray_m /= np.linalg.norm(ray_m)

        mesh = trimesh.load(root / "input" / m["mesh"], force="mesh")
        hull = np.asarray(mesh.convex_hull.vertices, np.float64)

        def low(tr: np.ndarray, ro: np.ndarray) -> np.ndarray:
            return (np.einsum("nij,kj->nki", ro, hull) + tr[:, None]) @ n_w + d_w

        def part(mask: np.ndarray) -> dict:
            if not mask.any():
                return {"frames": 0}
            o = e[mask].mean(0)
            return {"frames": int(mask.sum()), "total_cm_p50": p50(np.linalg.norm(e[mask], axis=1)),
                    "offset_cm": cm(np.linalg.norm(o)), "offset_vertical_cm": cm(o @ n_w),
                    "residual_cm_p50": p50(np.linalg.norm(e[mask] - o, axis=1)),
                    "rot_deg_p50": round(float(np.median(rot_deg(orr[mask], rr[mask]))), 1)}

        row = {"episode": name, "frames": int(n), "object_frames": int(vis.sum()), "calib_scale": round(s, 4),
               "total_cm_p50": p50(np.linalg.norm(e[vis], axis=1)),
               "total_cm_mean": cm(np.linalg.norm(e[vis], axis=1).mean()),  # what MP-SR averages over frames
               "total_cm_rms": cm(np.sqrt((np.linalg.norm(e[vis], axis=1) ** 2).mean())),
               "offset_cm": cm(np.linalg.norm(off)), "offset_vertical_cm": cm(off @ n_w),
               "offset_along_ray_cm": cm(off @ ray_m),
               "offset_across_ray_horizontal_cm": cm(np.linalg.norm(off - n_w * (off @ n_w) - ray_m * (off @ ray_m))),
               "drift_cm_rms": cm(np.sqrt((np.linalg.norm(drift[vis], axis=1) ** 2).mean())),
               "jitter_cm_rms": cm(np.sqrt((np.linalg.norm(jit[vis], axis=1) ** 2).mean())),
               "residual_along_ray_cm_rms": cm(np.sqrt(((res[vis] * ray).sum(1) ** 2).mean())),
               "static": part(static), "moving": part(moving),
               "static_segments": [], "visible_runs": len(runs(vis))}
        if static.any():
            hs, hr = low(ot[static], orr[static]).min(1), low(rt[static], rr[static]).min(1)
            row["static"]["lowest_above_floor_ours_cm_p50"] = p50(hs)
            row["static"]["lowest_above_floor_ref_cm_p50"] = p50(hr)
        for a, b in runs(static):
            o = e[a:b].mean(0)
            row["static_segments"].append({"start": int(a), "frames": int(b - a), "offset_cm": cm(np.linalg.norm(o)),
                                           "offset_vertical_cm": cm(o @ n_w),
                                           "jitter_cm_rms": cm(np.sqrt((np.linalg.norm(e[a:b] - o, axis=1) ** 2).mean()))})
        rows.append(row)
        print(json.dumps({k: v for k, v in row.items() if k != "static_segments"}), flush=True)
    out.write_text(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()
