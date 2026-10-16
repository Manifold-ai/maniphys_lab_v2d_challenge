"""Which intrinsics agree best with the released floor plane (Tier 3 inputs only; report only; CPU).

The released ground plane was made with the true camera, so among candidate intrinsics the one under which objects
resting on the floor land on it is the closest the Tier 3 inputs can tell. Method and re-expression are rxzhou's
t3_floor_tilt_k.py (branch track2/p1-training, md5 f4fafc1f): each floor event (t3_camera_height.py event_rows) takes
CARI4D's camera-frame pose T (official mesh local frame, intrinsics K_c), keeps the mesh origin's pixel p = K_c t, moves it
onto the ray K^-1 [p, 1] of the candidate K and turns the orientation with the ray. Depth:
  size   z = z_c * f / f_c   (CARI4D's depth set by the mesh's apparent size: scales with f)
  keep   z = z_c             (CARI4D's depth taken as metric, e.g. from MoGe)
The contact point is the convex hull vertex lowest along the current floor normal; a plane is fitted per variant (each
episode weighted equally, Huber 3 cm, 5 reweights, 3 normal iterations), and compared with the released plane: tilt split
into pitch (with depth) and roll (sideways), contact heights over the released plane (median, MAD), height slope with depth.
What each part can see: the principal point turns rays, which shows as pitch/roll and as a slope of height with depth;
f under "size" scales every point about the camera, which shows as a uniform height offset (~d_rel * df/f, 1.4 cm per 1 %),
and that offset also absorbs any bias of CARI4D's own depth, so f is told apart less firmly than the principal point.

Differences from t3_floor_tilt_k.py: the released plane is read from the Tier 3 input through t3_inputs (that script
reads it from the Tier 2 dataset directory), the guard is forbid_lower_tiers, and the variants are a grid.

    python t3_intrinsics_floor.py <tier3 root> [events json, default runs/camera_groups/camera_height_main.json]
Last line INTRINSICS_FLOOR_DONE.
"""

import json
import math
import sys
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

sys.path.insert(0, str(Path(__file__).resolve().parent))
import t3_inputs  # noqa: E402

HUBER_M = 0.03
FOCALS = {"MoGe 821": 821.0, "chosen 830": 830.0, "ceiling VP 851.3": 851.3, "ceiling grid 866.3": 866.3, "DA3 882.5": 882.5}
PRINCIPAL = {"centre (768, 576)": (768.0, 576.0), "cy only (768, 531.1)": (768.0, 531.1), "grid GB (701.8, 531.1)": (701.8, 531.1)}


def unit(v):
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


def ray_turn(a, b):
    a, b = unit(a), unit(b)
    ax = np.cross(a, b)
    s = np.linalg.norm(ax)
    return Rotation.from_rotvec(ax / s * math.atan2(s, float(a @ b)) if s > 1e-12 else np.zeros(3)).as_matrix()


def reexpress(T, kc, f, cx, cy, depth):
    t, R = T[:3, 3], T[:3, :3]
    fc = float(kc[0, 0])
    if depth == "focal step":  # t3_convert_ep.py focal: principal point kept, depth times f / f_c
        t2 = t * np.array([1.0, 1.0, f / fc])
    else:
        p = kc @ t
        r = np.linalg.inv(np.array([[f, 0, cx], [0, f, cy], [0, 0, 1.0]])) @ np.array([p[0] / p[2], p[1] / p[2], 1.0])
        t2 = r * (t[2] * (f / fc if depth == "size" else 1.0)) / r[2]
    return ray_turn(t, t2) @ R, t2


def fit_plane(p, w, up):
    ww = w.copy()
    for _ in range(5):
        c = (p * ww[:, None]).sum(0) / ww.sum()
        n = np.linalg.eigh(((p - c) * ww[:, None]).T @ (p - c))[1][:, 0]
        n = n if n @ up > 0 else -n
        d = -float(n @ c)
        ww = w * np.minimum(1.0, HUBER_M / np.maximum(np.abs(p @ n + d), 1e-9))
    return n, d


def main() -> None:
    import trimesh
    root = Path(sys.argv[1])
    events = Path(sys.argv[2]) if len(sys.argv) > 2 else root / "runs/camera_groups/camera_height_main.json"
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "libs" / "v2d_infra"))
    from tier_guard import forbid_lower_tiers
    forbid_lower_tiers()  # Tier 3: nothing from Tier 1 or Tier 2 (Kaggle 2.8.c)

    metas = {f"ep{m['episode_index']:02d}_{m['object']}": m for m in
             map(json.loads, (root / "input/meta/episodes_metadata.jsonl").read_text().splitlines()) if m}
    main_group = json.loads((root / "runs/floor/focal.json").read_text())["camera_groups"]["0"]
    planes = np.array([t3_inputs.ground_plane(root, metas[e]) for e in main_group])
    k = np.linalg.norm(planes[:, :3], axis=1)
    normals = planes[:, :3] / k[:, None] * np.sign(-planes[:, 1:2])  # up = -y in the OpenCV camera frame
    n_rel = unit(normals.mean(0))
    d_rel = float(np.median(np.abs(planes[:, 3] / k)))
    rows = json.loads(events.read_text())["event_rows"]
    eps = sorted({r["episode"] for r in rows})
    data = {}
    for ep in eps:
        oc = np.load(root / "runs/convert" / ep / "object_cam.npz")
        hull = np.asarray(trimesh.load(root / "input" / metas[ep]["mesh"], force="mesh").convex_hull.vertices, np.float64)
        data[ep] = (oc["T_cam_glb"].astype(np.float64), oc["intrinsics"].astype(np.float64).reshape(3, 3), hull)
    kc0 = data[eps[0]][1]
    print(f"== {len(rows)} floor events, {len(eps)} episodes; released n = ({n_rel[0]:+.5f}, {n_rel[1]:+.5f}, {n_rel[2]:+.5f}), "
          f"d {d_rel:.4f} m over {len(main_group)} main-camera episodes; CARI4D K_c of {eps[0]}: f {kc0[0, 0]:.1f}, "
          f"c ({kc0[0, 2]:.1f}, {kc0[1, 2]:.1f})")

    variants = [("control: pipeline focal step 830 (should give ~3.83 deg)", 830.0, 768.0, 576.0, "focal step")]
    for depth in ("size", "keep"):
        for pn, (cx, cy) in PRINCIPAL.items():
            for fn, f in FOCALS.items():
                variants.append((f"{depth:4s} | {pn:22s} | {fn}", f, cx, cy, depth))
    results = []
    for name, f, cx, cy, depth in variants:
        poses = {}
        for r in rows:
            T, kc, _ = data[r["episode"]]
            poses.setdefault(r["episode"], []).append(reexpress(T[r["frame"]], kc, f, cx, cy, depth))
        up = n_rel.copy()
        for _ in range(3):
            pts, w, epi = [], [], []
            for ep, plist in poses.items():
                hull = data[ep][2]
                for R, t in plist:
                    X = hull @ R.T + t
                    pts.append(X[np.argmin(X @ up)])
                    w.append(1.0 / len(plist))
                    epi.append(ep)
            pts, w = np.array(pts), np.array(w)
            up, d = fit_plane(pts, w, n_rel)
        tilt = math.degrees(math.acos(min(1.0, float(up @ n_rel))))
        pitch = math.degrees(math.atan2(up[2], -up[1]) - math.atan2(n_rel[2], -n_rel[1]))
        roll = math.degrees(math.atan2(up[0], -up[1]) - math.atan2(n_rel[0], -n_rel[1]))
        h = pts @ n_rel + d_rel
        slope = np.polyfit(pts[:, 2], h, 1, w=w)[0]
        med = float(np.median(h))
        per_ep = [float(np.median(h[np.array(epi) == e])) for e in eps]
        row = {"variant": name, "f": f, "cx": cx, "cy": cy, "depth": depth, "tilt_deg": round(tilt, 2), "pitch_deg": round(pitch, 2),
               "roll_deg": round(roll, 2), "height_med_cm": round(100 * med, 1), "height_mad_cm": round(100 * float(np.median(np.abs(h - med))), 1),
               "slope_cm_per_m": round(100 * slope, 2), "per_episode_median_cm_p10_p90": [round(100 * x, 1) for x in np.percentile(per_ep, [10, 90])],
               "fitted_d_minus_released_cm": round(100 * (d - d_rel), 1)}
        results.append(row)
        print(f"  {name}: tilt {tilt:.2f} (pitch {pitch:+.2f}, roll {roll:+.2f}); height median {100 * med:+.1f} cm, MAD "
              f"{row['height_mad_cm']:.1f}, per-episode p10..p90 {row['per_episode_median_cm_p10_p90']}; slope {100 * slope:+.2f} cm/m")
    out = root / "dev" / "intrinsics_floor.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"events": str(events), "n_events": len(rows), "episodes": eps, "results": results}, indent=1))
    print(f"wrote {out}")
    print("INTRINSICS_FLOOR_DONE")


if __name__ == "__main__":
    main()
