"""The floor of our Tier 3 reconstruction, per exo camera, and the correction that puts it on the released ground plane.

rxzhou's Tier 3 pilot (SOP 10/9) found resting objects floating 115-146 mm above the floor after retargeting. In the
camera-frame reconstruction the lowest point of floor-resting objects rises with depth (714 main-camera events: 3.8
deg, -3 cm at the camera), so our floor is tilted against the released plane. The correction keeps the camera at the
origin: rotate our floor normal onto the released one (smallest rotation), then scale positions by released offset /
our offset. Sizes (meshes, bodies) are not scaled. Yaw and horizontal position are not observable from a floor and stay
as they are.

Inputs are Tier 3 only: floor-resting events from t3_camera_height.py (object still in its mask, clear of the person,
render agrees with the mask, near the floor), CARI4D's object poses after the focal step of t3_convert_ep.py
(object_cam_focal.npz), the official meshes, the released ground plane.
Per camera group (t3_camera_groups.py), one contact point per event: the mesh vertex lowest along the current floor
normal (iterated from the released normal). Plane by iteratively reweighted (Huber) least squares, each episode weighted
equally. A group whose contact points span less than MIN_SPAN_M in either floor direction cannot fix a tilt; it keeps
MoGe's floor normal (t3 MoGe ground probe, also Tier 3) and fits only the offset.

Validation without reference: for every episode with events, the correction fitted with that episode left out is
applied to its own contact points; their height above the released plane should be near zero at every depth.

    python t3_floor_fit.py <tier3 root> <out .json> [convert dir under runs/, default convert]
The convert dir names whose focal step is fitted (10-16: runs/convert_kgb holds the focal step under the calibrated
main-camera intrinsics, runs/convert the f 830 one).
"""

import json
import t3_inputs  # noqa: E402  (same directory: released inputs Tier 3 may read)
import sys
from pathlib import Path

import numpy as np
import trimesh
from scipy.spatial.transform import Rotation

MIN_SPAN_M = 0.5
HUBER_M = 0.03


def plane_up(n: np.ndarray, d: float) -> tuple[np.ndarray, float]:
    k = np.linalg.norm(n)
    n, d = n / k, d / k
    return (n, d) if d > 0 else (-n, -d)


def fit_plane(p: np.ndarray, w: np.ndarray, normal: np.ndarray | None = None) -> tuple[np.ndarray, float]:
    """Weighted plane n.x + d = 0 through points; with `normal` given, only d."""
    ww = w.copy()
    for _ in range(30):
        c = (p * ww[:, None]).sum(0) / ww.sum()
        if normal is None:
            cov = ((p - c) * ww[:, None]).T @ (p - c)
            n = np.linalg.eigh(cov)[1][:, 0]
        else:
            n = normal
        n, d = plane_up(n, -float(n @ c))
        r = np.abs(p @ n + d)
        ww = w * np.minimum(1.0, HUBER_M / np.maximum(r, 1e-9))
    return n, d


def correction(n_ours: np.ndarray, d_ours: float, n_rel: np.ndarray, d_rel: float) -> tuple[np.ndarray, float]:
    rot = Rotation.align_vectors([n_rel], [n_ours])[0].as_matrix()
    return rot, d_rel / d_ours


def main() -> None:
    root, out = Path(sys.argv[1]), Path(sys.argv[2])
    conv_dir = root / "runs" / (sys.argv[3] if len(sys.argv) > 3 else "convert")
    groups = json.loads((root / "runs/camera_groups/camera_groups.json").read_text())["groups"]
    metas = {f"ep{m['episode_index']:02d}_{m['object']}": m for m in
             map(json.loads, (root / "input/meta/episodes_metadata.jsonl").read_text().splitlines()) if m}
    moge = {r["episode_index"]: r for r in json.loads((root / "runs/moge_ground/moge_ground_probe.json").read_text())}
    events = []
    for f in sorted((root / "runs/camera_groups").glob("camera_height_*.json")):
        events += json.loads(f.read_text())["event_rows"]
    report = {"groups": [], "episodes": {}}
    for gi, members in enumerate(groups):
        ev = [e for e in events if e["episode"] in members]
        planes = {}
        for name in members:
            gp = t3_inputs.ground_plane(root, metas[name])
            planes[name] = plane_up(np.asarray(gp[:3], np.float64), float(gp[3]))
        n_rel = plane_up(np.mean([p[0] for p in planes.values()], 0), float(np.mean([p[1] for p in planes.values()])))[0]
        d_rel = float(np.median([p[1] for p in planes.values()]))
        cache = {}
        pts_by_ep = {}
        for e in ev:
            name = e["episode"]
            if name not in cache:
                m = metas[name]
                cache[name] = (np.load(conv_dir / name / "object_cam_focal.npz")["T_cam_glb"],
                               np.asarray(trimesh.load(root / "input" / m["mesh"], force="mesh").convex_hull.vertices, np.float64))
            poses, hull = cache[name]
            t = poses[e["frame"]]
            pts_by_ep.setdefault(name, []).append(hull @ t[:3, :3].T + t[:3, 3])
        if not pts_by_ep:
            report["groups"].append({"group": gi, "members": members, "events": 0, "note": "no floor events; no correction"})
            continue

        def contact_points(names: list[str], normal: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
            p, w = [], []
            for nm in names:
                vs = pts_by_ep[nm]
                p += [v[np.argmin(v @ normal)] for v in vs]
                w += [1.0 / len(vs)] * len(vs)
            return np.array(p), np.array(w)

        def fit(names: list[str]) -> tuple[np.ndarray, float, str, np.ndarray]:
            normal = n_rel
            for _ in range(3):
                p, w = contact_points(names, normal)
                c = (p * w[:, None]).sum(0) / w.sum()
                span = np.linalg.svd((p - c) * np.sqrt(w)[:, None] / np.sqrt(w.sum()), compute_uv=False)
                if span[1] < MIN_SPAN_M / 2:  # std along the second floor direction: cannot fix a tilt
                    mn = [plane_up(np.asarray(moge[metas[nm]["episode_index"]]["n_moge"], np.float64), 1.0)[0] for nm in names
                          if metas[nm]["episode_index"] in moge]
                    normal = plane_up(np.mean(mn, 0), 1.0)[0]
                    n, d = fit_plane(p, w, normal)
                    return n, d, "moge_normal_offset_from_contacts", span
                n, d = fit_plane(p, w)
                normal = n
            return n, d, "contacts", span

        names_with = sorted(pts_by_ep)
        n_o, d_o, how, span = fit(names_with)
        rot, s = correction(n_o, d_o, n_rel, d_rel)
        g = {"group": gi, "members": members, "events": len(ev), "episodes_with_events": names_with, "how": how,
             "contact_span_std_m": span.round(3).tolist(), "n_ours": n_o.round(5).tolist(), "d_ours_m": round(d_o, 4),
             "n_released": n_rel.round(5).tolist(), "d_released_m": round(d_rel, 4),
             "tilt_deg": round(float(np.degrees(np.arccos(np.clip(n_o @ n_rel, -1, 1)))), 3), "scale": round(s, 5),
             "rotation": rot.round(8).tolist()}
        # leave-one-episode-out validation on each episode's own contact points
        val = {}
        for nm in names_with:
            rest = [x for x in names_with if x != nm]
            if not rest:
                continue
            n2, d2, _, _ = fit(rest)
            r2, s2 = correction(n2, d2, n_rel, d_rel)
            p, _ = contact_points([nm], n2)
            n_w, d_w = planes[nm]
            h_before = p @ n_w + d_w
            h_after = (s2 * p @ r2.T) @ n_w + d_w
            z = p[:, 2]
            val[nm] = {"events": len(p), "depth_m_median": round(float(np.median(z)), 2),
                       "height_before_m_median": round(float(np.median(h_before)), 4),
                       "height_after_loo_m_median": round(float(np.median(h_after)), 4),
                       "height_after_loo_m_p10_p90": np.percentile(h_after, [10, 90]).round(4).tolist()}
        g["validation_leave_one_out"] = val
        if len(val) >= 3:
            hb = np.concatenate([[v["height_before_m_median"]] for v in val.values()])
            ha = np.concatenate([[v["height_after_loo_m_median"]] for v in val.values()])
            g["validation_summary"] = {"episodes": len(val), "before_abs_median_m": round(float(np.median(np.abs(hb))), 4),
                                       "after_abs_median_m": round(float(np.median(np.abs(ha))), 4),
                                       "after_abs_max_m": round(float(np.max(np.abs(ha))), 4)}
        report["groups"].append(g)
        for nm in members:
            report["episodes"][nm] = {"group": gi, "rotation": g["rotation"], "scale": g["scale"], "tilt_deg": g["tilt_deg"],
                                      "how": how, "own_events": nm in pts_by_ep}
        print(json.dumps({k: v for k, v in g.items() if k not in ("rotation", "validation_leave_one_out", "members")}), flush=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
