"""Do the second and side exo cameras share the main camera's calibrated intrinsics? Floor checks against the main view
(dev probe, 10-16; Tier 3 inputs and CARI4D output only).

Why not "floor contacts vs horizon" in the other camera alone: CARI4D's points and the image horizon come from the same
pixels, and a change of intrinsics maps both by the same linear map, so they agree under any intrinsics. A check needs a
measurement made through the main camera, whose intrinsics (rxzhou's ceiling grid GB) and world (its camera frame, the
released floor; floor_fit_kgb.json) are trusted:
  A  main sees camera X (people-free plate, Grounding DINO 'tripod' holding a 'camera' box, dev/walls/det_plate_*): the
     tripod's bottom edge on the released floor gives the foot, its width the leg circle r = spread / sqrt(3), the centre
     lies r/2 (two legs in front) to r (one leg in front) beyond the foot; the camera box centre's ray, cut where it is
     above that centre, gives X's head height over the floor. Both ends of the centre interval are reported.
  B  X's own height: its floor events (t3_camera_height.py, camera_height_B / _C) re-expressed from CARI4D's camera
     frame under candidate intrinsics (t3_convert_ep._intrinsics_map: pixels kept, depth scaled with f), the contact plane
     fitted as t3_floor_fit.py does (lowest hull vertex, Huber, normal iterated, each episode equally) -> its distance.
     Same for the main camera as a control (should give its released height, up to CARI4D's own depth bias: 1.6 % in
     floor_fit_kgb.json).
  C  X sees the main camera: the main tripod's foot on X's own fitted floor -> range, to set against A's range.
  D  the side camera sees both others: the distance between the two tripod centres on its own floor, to set against the
     main-to-second distance from A.
X's head height in A should equal its height in B (camera box centre vs optical centre: a few cm), and the ranges in C
and A should agree, for the intrinsics X really has. Candidates: GB, and CARI4D's own (MoGe-based, per episode).

    python t3_register_check.py <tier3 root>     (gate venv: numpy, scipy, trimesh)
Writes dev/register_check/register_check.json; last line REGISTER_CHECK_DONE.
"""

import json
import sys
from pathlib import Path

import numpy as np
import trimesh

sys.path.insert(0, str(Path(__file__).resolve().parent))
import t3_inputs  # noqa: E402
from t3_convert_ep import _intrinsics_map  # noqa: E402

GB = np.array([[866.3, 0, 701.8], [0, 866.3, 531.1], [0, 0, 1.0]])
HUBER_M = 0.03


def plane_up(n, d):
    k = np.linalg.norm(n)
    n, d = n / k, d / k
    return (n, d) if d > 0 else (-n, -d)


def fit_plane(p, w):
    ww = w.copy()
    for _ in range(30):
        c = (p * ww[:, None]).sum(0) / ww.sum()
        n = np.linalg.eigh(((p - c) * ww[:, None]).T @ (p - c))[1][:, 0]
        n, d = plane_up(n, -float(n @ c))
        ww = w * np.minimum(1.0, HUBER_M / np.maximum(np.abs(p @ n + d), 1e-9))
    return n, d


def own_floor(root, metas, events, k_of):
    """Contact plane of one camera's floor events in its own camera frame under intrinsics k_of(ep, K_c)."""
    by_ep = {}
    for e in events:
        by_ep.setdefault(e["episode"], []).append(e["frame"])
    pts_ep = {}
    for ep, frames in by_ep.items():
        oc = np.load(root / "runs/convert" / ep / "object_cam.npz")
        kc = np.asarray(oc["intrinsics"], float).reshape(3, 3)
        m = _intrinsics_map(kc, k_of(ep, kc))
        T = oc["T_cam_glb"].astype(float)
        hull = np.asarray(trimesh.load(root / "input" / metas[ep]["mesh"], force="mesh").convex_hull.vertices, float)
        X = []
        for f in frames:
            R, t = T[f, :3, :3], T[f, :3, 3]
            t2 = m @ t
            a, b = t / np.linalg.norm(t), t2 / np.linalg.norm(t2)  # orientation turns with the ray
            v = np.cross(a, b); s = np.linalg.norm(v); c = float(a @ b)
            vx = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
            turn = np.eye(3) + vx + vx @ vx * ((1 - c) / (s * s) if s > 1e-12 else 0.0)
            X.append(hull @ (turn @ R).T + t2)
        pts_ep[ep] = X
    up = np.array([0.0, -1.0, 0.0])
    for _ in range(4):
        p, w = [], []
        for ep, Xs in pts_ep.items():
            for X in Xs:
                p.append(X[np.argmin(X @ up)]); w.append(1.0 / len(Xs))
        up, d = fit_plane(np.array(p), np.array(w))
    return up, d, {ep: len(v) for ep, v in pts_ep.items()}


def floor_frame(n, d):
    o = -d * n
    u = np.array([1.0, 0, 0]) - n[0] * n; u /= np.linalg.norm(u)
    return o, u, np.cross(n, u)


def sightings(det):
    """Every 'camera' box with a 'tripod' box under it, best tripod per camera."""
    cams = [x for x in det if x["label"].strip() == "camera"]
    tris = [x for x in det if "tripod" in x["label"]]
    out = []
    for c in sorted(cams, key=lambda x: -x["confidence"]):
        cb = c["box"]; cx = (cb["x0"] + cb["x1"]) / 2
        under = [t for t in tris if t["box"]["x0"] - 5 <= cx <= t["box"]["x1"] + 5 and t["box"]["y0"] >= cb["y0"] - 10]
        if not under:
            continue
        tb = max(under, key=lambda x: x["confidence"])["box"]
        if any(abs((o["cam"]["x0"] + o["cam"]["x1"]) / 2 - cx) < 30 for o in out):
            continue  # same camera, lower-confidence box
        out.append({"cam": cb, "tri": tb, "conf": round(c["confidence"], 2)})
    return out


def measure(sig, K, Rw, n, d):
    """Floor geometry of one sighting in a camera whose rays are Rw @ K^-1 p and whose floor is n.X + d = 0 (n up)."""
    o, u, v = floor_frame(n, d)
    Ki = np.linalg.inv(K)
    ray = lambda px: Rw @ (Ki @ np.array([px[0], px[1], 1.0]))
    def on_floor(px):
        r = ray(px)
        X = (-d / (n @ r)) * r
        return np.array([(X - o) @ u, (X - o) @ v])
    tb, cb = sig["tri"], sig["cam"]
    foot = on_floor(((tb["x0"] + tb["x1"]) / 2, tb["y1"]))
    spread = float(np.linalg.norm(on_floor((tb["x1"], tb["y1"])) - on_floor((tb["x0"], tb["y1"]))))
    r_leg = spread / np.sqrt(3.0)
    rng = float(np.linalg.norm(foot))
    hr = ray(((cb["x0"] + cb["x1"]) / 2, (cb["y0"] + cb["y1"]) / 2))
    hh = np.array([hr @ u, hr @ v])  # horizontal component per unit lambda
    heights = []
    for delta in (r_leg / 2, r_leg):
        lam = (rng + delta) / np.linalg.norm(hh)
        heights.append(float(n @ (lam * hr) + d))
    return {"range_foot_m": round(rng, 3), "centre_m": [round(rng + r_leg / 2, 3), round(rng + r_leg, 3)],
            "bearing_deg": round(float(np.degrees(np.arctan2(foot[1], foot[0]))), 2), "leg_r_m": round(r_leg, 3),
            "head_height_m": [round(h, 3) for h in heights]}


def main() -> None:
    root = Path(sys.argv[1])
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "libs" / "v2d_infra"))
    from tier_guard import forbid_lower_tiers
    forbid_lower_tiers()
    metas = {f"ep{m['episode_index']:02d}_{m['object']}": m for m in
             map(json.loads, (root / "input/meta/episodes_metadata.jsonl").read_text().splitlines()) if m}
    groups = json.loads((root / "runs/camera_groups/camera_groups.json").read_text())["groups"]
    fit = json.loads((root / "runs/floor/floor_fit_kgb.json").read_text())
    det_dir = root / "dev/walls"
    report = {}

    # A: main camera's sightings, in its world (rays rotated by the floor correction, the released floor)
    rows = []
    for ep in groups[0]:
        f = det_dir / f"det_plate_{ep}.json"
        if not f.exists():
            continue
        e = fit["episodes"][ep]
        R, s = np.asarray(e["rotation"]), float(e["scale"])
        n, d = plane_up(*np.split(np.asarray(t3_inputs.ground_plane(root, metas[ep]), float), [3]))
        d = float(d[0]) if np.ndim(d) else float(d)
        for sg in sightings(json.loads(f.read_text())):
            rows.append({"ep": ep, **measure(sg, GB, s * R, n, d)})
    report["A_main_sees"] = rows
    print("A main sees (GB, released floor, floor_fit_kgb):")
    for r in rows:
        print("  ", json.dumps(r))

    # B: own floor heights under candidate intrinsics
    events = {g: json.loads((root / "runs/camera_groups" / f"camera_height_{g}.json").read_text())["event_rows"] for g in ("main", "B", "C")}
    cands = {"GB": lambda ep, kc: GB, "CARI4D own": lambda ep, kc: kc,
             "CARI4D own f, GB principal point": lambda ep, kc: np.array([[kc[0, 0], 0, GB[0, 2]], [0, kc[0, 0], GB[1, 2]], [0, 0, 1.0]])}
    own = {}
    for g in ("main", "B", "C"):
        for cn, kf in cands.items():
            n2, d2, cnt = own_floor(root, metas, events[g], kf)
            own[(g, cn)] = (n2, d2)
            pitch = float(np.degrees(np.arctan2(n2[2], -n2[1]))); roll = float(np.degrees(np.arctan2(n2[0], -n2[1])))
            report.setdefault("B_own_floor", []).append({"camera": g, "intrinsics": cn, "height_m": round(d2, 4),
                                                         "pitch_deg": round(pitch, 2), "roll_deg": round(roll, 2), "events": cnt})
            print(f"B own floor {g:4s} {cn:34s}: height {d2:.4f} m, pitch {pitch:+.2f}, roll {roll:+.2f}  events {cnt}")

    # C, D: the other cameras' sightings on their own floors
    for g, gi in (("B", 1), ("C", 2)):
        for cn, kf in cands.items():
            n2, d2 = own[(g, cn)]
            out = []
            for ep in groups[gi]:
                f = det_dir / f"det_plate_{ep}.json"
                if not f.exists():
                    continue
                kc = np.asarray(np.load(root / "runs/convert" / ep / "object_cam.npz")["intrinsics"], float).reshape(3, 3)
                for sg in sightings(json.loads(f.read_text())):
                    out.append({"ep": ep, **measure(sg, kf(ep, kc), np.eye(3), n2, d2)})
            report.setdefault("C_D_other_sees", []).append({"camera": g, "intrinsics": cn, "sightings": out})
            print(f"{'C' if g == 'B' else 'D'} {g} sees ({cn}):")
            for r in out:
                print("  ", json.dumps(r))
    outp = root / "dev/register_check/register_check.json"
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(report, indent=1, default=float))
    print("wrote", outp)
    print("REGISTER_CHECK_DONE")


if __name__ == "__main__":
    main()
