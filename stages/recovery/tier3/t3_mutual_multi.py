"""Mutual sightings over all episodes of two exo cameras (dev probe, Tier 3 inputs only).

Per plate: the top 'tripod' box that holds the top 'camera' box; the tripod's bottom edge meets the floor at the other
camera's floor position (bearing from the camera box centre's column, range from the foot). Per camera, the median over
its episodes; an episode whose foot reads far from the median is a partly hidden tripod and is reported as such.
yaw = angle(-p21) - angle(p12). Range: the tripod box's bottom edge is the leg tip nearest to the viewer, not the
tripod's centre. With three legs spread over a circle of radius r (the box spans r * sqrt(3) across), the centre lies
r/2 (two legs in front) to r (one leg in front) beyond the foot. Each direction gives an interval [foot + r/2, foot + r];
both directions measure the same distance, so the range is the midpoint of their intersection.
Writes the camera_register.json entry for group b onto group a when an output path is given.
    python t3_mutual_multi.py <tier3 root> <floor_fit.json> <det dir> <group a> <group b> [camera_register.json]
"""
import json, sys
import t3_inputs  # noqa: E402  (same directory: released inputs Tier 3 may read)
from pathlib import Path
import numpy as np

root, fit_path, det_dir, ga, gb = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
fit = json.loads(fit_path.read_text())
meta = {f"ep{m['episode_index']:02d}_{m['object']}": m for m in map(json.loads, (root / "input/meta/episodes_metadata.jsonl").read_text().splitlines()) if m}

def basis(ep):
    gp = np.asarray(t3_inputs.ground_plane(root, meta[ep]), float)
    n, d = gp[:3] / np.linalg.norm(gp[:3]), gp[3] / np.linalg.norm(gp[:3])
    if d < 0: n, d = -n, -d
    u = np.array([1.0, 0, 0]) - n[0] * n; u /= np.linalg.norm(u)
    return n, d, -d * n, u, np.cross(n, u)

def sight(ep):
    f = det_dir / f"det_plate_{ep}.json"
    if not f.exists(): return None
    dets = json.load(open(f))
    cams = [x for x in dets if x["label"].strip() == "camera"]
    if not cams: return None
    cam = max(cams, key=lambda x: x["confidence"]); cb = cam["box"]; cx = (cb["x0"] + cb["x1"]) / 2
    tris = [x for x in dets if "tripod" in x["label"] and x["box"]["x0"] - 5 <= cx <= x["box"]["x1"] + 5 and x["box"]["y0"] >= cb["y0"] - 10]
    if not tris: return None
    tb = max(tris, key=lambda x: x["confidence"])["box"]
    e = fit["episodes"][ep]; R, s = np.asarray(e["rotation"]), float(e["scale"])
    K = np.asarray(np.load(root / "runs/convert" / ep / "object_cam_focal.npz")["intrinsics"])
    n, d, o, u, v = basis(ep)
    def on_floor(px):
        ray = s * (R @ (np.linalg.inv(K) @ np.array([px[0], px[1], 1.0])))
        X = (-d / (n @ ray)) * ray
        return np.array([(X - o) @ u, (X - o) @ v])
    foot = on_floor(((tb["x0"] + tb["x1"]) / 2, tb["y1"]))
    # bearing from the camera box column on the floor ray at an arbitrary range (column decides the azimuth)
    head_dir = on_floor((cx, max(tb["y1"], 700.0)))
    left, right = on_floor((tb["x0"], tb["y1"])), on_floor((tb["x1"], tb["y1"]))
    return {"ep": ep, "foot_m": foot, "spread_m": float(np.linalg.norm(right - left)), "range_m": float(np.linalg.norm(foot)), "bearing_deg": float(np.degrees(np.arctan2(foot[1], foot[0]))),
            "bearing_cam_deg": float(np.degrees(np.arctan2(head_dir[1], head_dir[0]))), "foot_y": tb["y1"]}

eps = lambda g: sorted(e for e, v in fit["episodes"].items() if v["group"] == g and (root / "runs/convert" / e / "object_world.npz").exists())
out = {}
for g in (ga, gb):
    rows = [r for r in (sight(e) for e in eps(g)) if r]
    rng = np.array([r["range_m"] for r in rows]); med = float(np.median(rng))
    good = [r for r in rows if abs(r["range_m"] - med) < 0.5]
    out[g] = {"n": len(rows), "n_good": len(good), "range_median_m": round(float(np.median([r["range_m"] for r in good])), 3),
              "range_iqr_m": np.percentile([r["range_m"] for r in good], [25, 75]).round(3).tolist(),
              "spread_median_m": round(float(np.median([r["spread_m"] for r in good])), 3),
              "bearing_median_deg": round(float(np.median([r["bearing_deg"] for r in good])), 2),
              "bearing_std_deg": round(float(np.std([r["bearing_deg"] for r in good])), 2),
              "outliers": [(r["ep"], round(r["range_m"], 2), r["foot_y"]) for r in rows if abs(r["range_m"] - med) >= 0.5]}
    print(f"camera group {g} sees the other:", json.dumps(out[g]))
b_ab, b_ba = out[ga]["bearing_median_deg"], out[gb]["bearing_median_deg"]
yaw = ((b_ab + 180) - b_ba) % 360
intervals = []
for g in (ga, gb):
    r = out[g]["spread_median_m"] / np.sqrt(3.0)
    intervals.append((out[g]["range_median_m"] + r / 2, out[g]["range_median_m"] + r))
lo, hi = max(i[0] for i in intervals), min(i[1] for i in intervals)
if lo > hi:
    raise SystemExit(f"tripod-centre intervals do not overlap: {intervals}")
rng = (lo + hi) / 2
t = rng * np.array([np.cos(np.radians(b_ab)), np.sin(np.radians(b_ab))])
res = {"fixed_group": ga, "moving_group": gb, "yaw_deg": round(yaw, 2), "t_m": t.round(4).tolist(), "range_m": round(rng, 3),
       "range_interval_m": [round(lo, 3), round(hi, 3)], "foot_range_mismatch_m": round(out[ga]["range_median_m"] - out[gb]["range_median_m"], 3)}
print(json.dumps(res))
if len(sys.argv) > 6:
    first = sorted(e for e, v in fit["episodes"].items() if v["group"] == ga)[0]
    gp = t3_inputs.ground_plane(root, meta[first])
    path = Path(sys.argv[6])
    spec = json.loads(path.read_text()) if path.exists() else {"note": "Floor-plane motions onto the main exo camera's world, "
           "applied by t3_convert_ep.py world after the floor correction (Tier 3 inputs only).", "groups": {}}
    spec["groups"][str(gb)] = {"to_group": ga, "yaw_deg": res["yaw_deg"], "t_m": res["t_m"],
                               "plane": {"from": f"{first} ground_plane", "n": gp[:3], "d": gp[3]},
                               "how": "t3_mutual_multi.py: mutual tripod-camera sightings on people-free plates",
                               "sightings": {str(g): {k: out[g][k] for k in ("n", "n_good", "range_median_m", "spread_median_m", "bearing_median_deg", "bearing_std_deg")} for g in (ga, gb)},
                               "range_interval_m": res["range_interval_m"],
                               "uncertainty": {"yaw_deg": round(float(np.hypot(out[ga]["bearing_std_deg"], out[gb]["bearing_std_deg"])), 2),
                                               "range_m": round((hi - lo) / 2, 3)}}
    path.write_text(json.dumps(spec, indent=1))
    print("wrote", path)
