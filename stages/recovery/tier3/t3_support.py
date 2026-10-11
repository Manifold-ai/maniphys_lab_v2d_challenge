"""Support surfaces from Tier 3 signals, and object penetration of the floor and of those supports (Tier 3 inputs only).

Tier 3 may not read the released support_surface files (they sit where the clean object rests: a clean trajectory in
disguise, see the handoff), so the supports are measured here. A static segment (every STATIC_WINDOW-frame window
in it keeps the object's positions within STATIC_RADIUS_M of the window's median; hands are not looked at, since a
hand usually stays by the object just before a pick and after a place; not a speed threshold, because CARI4D's pose
jitters ~5 mm per frame at rest, 15 cm/s, while staying within a few cm) whose lowest hull point is more than FLOOR_TOL_M above the
floor is the object standing on something: that height is the support's, the hull's footprint at the segment's median
pose is a patch of it. The share of its frames with a hand within the physics check's HOLD_M is reported (a held object
kept still in the air also reads as static). Segments of one episode at heights within MERGE_DH_M and footprints within MERGE_XY_M are one support; its patch
is the convex hull of their footprints, grown by PATCH_MARGIN_M.

Penetration, per frame, from the physics check's lowest hull point:
  floor     lowest point more than FLOOR_TOL_M below the floor (as object_floor_penetration);
  support   object centre over a support's patch and lowest point more than FLOOR_TOL_M below the support.
Cross-check (independent of the object): MoGe-2 on the people-free plate (t3_walls.py moge), turned onto the released
floor as t3_walls.py does and moved by camera_register.json for registered cameras; its horizontal points (normal within
MOGE_NORMAL_DEG of up) over the patch give the table height seen from the image: `confirmed` within MOGE_AGREE_M of the
support; `below_surface` when the object's bottom is more than that below it (sunk into the table, or MoGe off);
`above_surface` when it is more than that above the surface under it (held still above a table); `no_surface` when the
image shows no horizontal surface there (held still above the floor). Static and held look alike from the object's
motion alone, so only `confirmed` and `below_surface` are supports; support penetration is counted against those.

    python t3_support.py <tier3 root> <version dir name> <physics dir> <walls dir> <out dir>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import t3_inputs  # noqa: E402

FLOOR_TOL_M = 0.03
STATIC_WINDOW = 15
STATIC_RADIUS_M = 0.05
MOGE_AGREE_M = 0.03
MERGE_DH_M = 0.03
MERGE_XY_M = 0.6
PATCH_MARGIN_M = 0.05
MOGE_NORMAL_DEG = 10.0
MOGE_MIN_H_M = 0.15
MOGE_BAND_M = 0.10
MOGE_MIN_POINTS = 200


def basis(gp):
    n, d = np.asarray(gp[:3], float), float(gp[3])
    k = np.linalg.norm(n); n, d = n / k, d / k
    if d < 0:
        n, d = -n, -d
    u = np.array([1.0, 0, 0]) - n[0] * n; u /= np.linalg.norm(u)
    return n, d, -d * n, u, np.cross(n, u)


def rot2(a):
    return np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]])


def hull2(pts):
    """Convex hull (monotone chain) of 2-D points, counter-clockwise."""
    p = sorted(map(tuple, np.round(pts, 6)))
    if len(p) < 3:
        return np.asarray(p)
    cross = lambda o, a, b: (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, up = [], []
    for q in p:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], q) <= 0: lo.pop()
        lo.append(q)
    for q in reversed(p):
        while len(up) >= 2 and cross(up[-2], up[-1], q) <= 0: up.pop()
        up.append(q)
    return np.asarray(lo[:-1] + up[:-1])


def inside(poly, pts, margin):
    """Points within `margin` of a convex counter-clockwise polygon (signed edge distances)."""
    a, b = poly, np.roll(poly, -1, 0)
    e = b - a; nrm = np.c_[e[:, 1], -e[:, 0]] / np.linalg.norm(e, axis=1)[:, None]  # outward for ccw
    dist = ((pts[:, None] - a[None]) * nrm[None]).sum(-1)
    return (dist <= margin).all(1)


def moge_world(wdir, name, gp, reg):
    """MoGe plate points as (plane coords in the main camera's world, height), horizontal ones only, as t3_walls.py."""
    from t3_walls import rot_onto
    f = wdir / f"moge_{name}.npz"
    if not f.exists():
        return None
    z = np.load(f)
    pts, mask, nrm = z["points"].astype(np.float64), z["mask"], z["normal"].astype(np.float64)
    h, w = mask.shape
    rows = np.arange(h)[:, None].repeat(w, 1)
    sel = mask & (rows > h * 0.55)
    cand = pts[sel][np.abs(nrm[sel] @ np.array([0.0, -1.0, 0.0])) > 0.9]
    rng = np.random.default_rng(0); best = (0, None)
    for _ in range(500):
        s3 = cand[rng.choice(len(cand), 3, replace=False)]
        nn = np.cross(s3[1] - s3[0], s3[2] - s3[0])
        if np.linalg.norm(nn) < 1e-9:
            continue
        nn /= np.linalg.norm(nn); dd = -nn @ s3[0]
        k = int((np.abs(cand @ nn + dd) < 0.03).sum())
        if k > best[0]:
            best = (k, (nn, dd))
    nn, dd = best[1]
    if dd < 0:
        nn, dd = -nn, -dd
    n_r, d_r, o, u, v = basis(gp)
    r = rot_onto(nn, n_r); s = d_r / dd
    world = (pts[mask] @ r.T) * s
    up = (nrm[mask] @ r.T) @ n_r
    horiz = up > np.cos(np.radians(MOGE_NORMAL_DEG))
    world = world[horiz]
    hgt = world @ n_r + d_r
    p = np.c_[(world - o) @ u, (world - o) @ v]
    if reg is not None:
        p = p @ rot2(np.radians(reg["yaw_deg"])).T + np.asarray(reg["t_m"])
    return p, hgt


def main() -> None:
    import trimesh
    from scipy.spatial.transform import Rotation

    root, version, phys, wdir, out = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3]), Path(sys.argv[4]), Path(sys.argv[5])
    out.mkdir(parents=True, exist_ok=True)
    metas = {m["episode_index"]: m for m in map(json.loads, (root / "input/meta/episodes_metadata.jsonl").read_text().splitlines()) if m}
    fit = json.loads((root / "runs/floor/floor_fit_f830.json").read_text())["episodes"]
    regs = json.loads((root / "runs/floor/camera_register.json").read_text())["groups"]
    main_gp = list(regs["1"]["plane"]["n"]) + [regs["1"]["plane"]["d"]]
    _, _, o_m, u_m, v_m = basis(main_gp)
    rows = []
    for f in sorted((phys / "npz").glob("episode_*.npz")):
        z = np.load(f)
        ep = int(z["episode_index"]); m = metas[ep]; name = f"ep{ep:02d}_{m['object']}"
        rep = json.loads((phys / "out" / f"{name}.json").read_text())
        pz = np.load(phys / "out" / f"{name}.npz")
        obj_low = pz["obj_low"]
        gp = t3_inputs.ground_plane(root, m)
        n, d, _, _, _ = basis(gp)
        pose = z["object_pose"]
        rot = Rotation.from_quat(np.c_[pose[:, 4:7], pose[:, 3:4]]).as_matrix(); pos = pose[:, :3]
        xy = np.c_[(pos - o_m) @ u_m, (pos - o_m) @ v_m]
        hull = np.asarray(trimesh.load(root / "input" / m["mesh"], force="mesh").convex_hull.vertices, np.float64)
        held = pz["held"]
        still = np.zeros(len(pos), bool)
        for i in range(len(pos) - STATIC_WINDOW + 1):
            w = pos[i:i + STATIC_WINDOW]
            if np.linalg.norm(w - np.median(w, 0), axis=1).max() < STATIC_RADIUS_M:
                still[i:i + STATIC_WINDOW] = True
        static = [(int(a), int(b)) for a, b in zip(*[iter(np.flatnonzero(np.diff(np.r_[0, still.astype(int), 0])))] * 2)]
        rest_on = {"floor": 0, "off_floor": 0, "below_floor": 0}
        segs = []
        for a, b in static:
            lo = float(np.median(obj_low[a:b]))
            on = "floor" if abs(lo) <= FLOOR_TOL_M else ("below_floor" if lo < 0 else "off_floor")
            rest_on[on] += b - a
            if on != "off_floor":
                continue
            k = a + int(np.argmin(np.linalg.norm(pos[a:b] - np.median(pos[a:b], 0), axis=1)))
            wv = hull @ rot[k].T + pos[k]
            foot = np.c_[(wv - o_m) @ u_m, (wv - o_m) @ v_m]
            segs.append({"start": a, "end": b, "height_m": lo, "footprint": hull2(foot), "centre": xy[k]})
        sups = []
        for sg in sorted(segs, key=lambda s: -(s["end"] - s["start"])):
            for sp in sups:
                if abs(sp["height_m"] - sg["height_m"]) < MERGE_DH_M and np.linalg.norm(sp["centre"] - sg["centre"]) < MERGE_XY_M:
                    sp["segs"].append(sg); break
            else:
                sups.append({"height_m": sg["height_m"], "centre": sg["centre"], "segs": [sg]})
        group = fit[name]["group"] if name in fit else 0
        mg = moge_world(wdir, name, gp, regs.get(str(group)))
        sup_out = []
        floor_pen = obj_low < -FLOOR_TOL_M
        sup_pen_any = np.zeros(len(obj_low), bool); sup_depth = np.zeros(len(obj_low))
        for i, sp in enumerate(sups):
            frames = np.concatenate([np.arange(s["start"], s["end"]) for s in sp["segs"]])
            h = float(np.median(obj_low[frames]))
            poly = hull2(np.concatenate([s["footprint"] for s in sp["segs"]]))
            cm = None
            if mg is not None:
                p, hg = mg
                sel = inside(poly, p, PATCH_MARGIN_M + 0.10) & (hg > MOGE_MIN_H_M) & (hg < h + MOGE_BAND_M)
                if sel.sum() >= MOGE_MIN_POINTS:
                    hist, edges = np.histogram(hg[sel], bins=np.arange(MOGE_MIN_H_M, h + MOGE_BAND_M + 0.01, 0.01))
                    peak = float(edges[np.argmax(np.convolve(hist, np.ones(3) / 3, "same"))] + 0.005)
                    cm = {"points": int(sel.sum()), "mode_height_m": round(peak, 3), "minus_support_m": round(peak - h, 3)}
            status = ("no_surface" if cm is None else "confirmed" if abs(cm["minus_support_m"]) <= MOGE_AGREE_M
                      else "below_surface" if cm["minus_support_m"] > 0 else "above_surface")
            over = inside(poly, xy, PATCH_MARGIN_M)
            pen = over & (obj_low < h - FLOOR_TOL_M) & (status in ("confirmed", "below_surface"))
            sup_pen_any |= pen; sup_depth = np.maximum(sup_depth, np.where(pen, h - obj_low, 0))
            sup_out.append({"support": i, "height_m": round(h, 3), "frames_at_rest": int(len(frames)), "held_share": round(float(held[frames].mean()), 2), "status": status,
                            "segments": [[s["start"], s["end"]] for s in sp["segs"]],
                            "patch_area_m2": round(float(0.5 * abs(np.dot(poly[:, 0], np.roll(poly[:, 1], 1)) - np.dot(poly[:, 1], np.roll(poly[:, 0], 1)))), 3) if len(poly) >= 3 else 0.0,
                            "patch_xy_m": poly.round(3).tolist(), "penetration_frames": int(pen.sum()),
                            "penetration_max_m": round(float((h - obj_low)[pen].max()), 3) if pen.any() else 0.0, "moge": cm})
        row = {"episode": name, "tier": rep["tier"], "frames": len(obj_low), "group": group, "rest_frames": rest_on,
               "floor_penetration_frames": int(floor_pen.sum()), "floor_penetration_max_m": round(float(-obj_low[floor_pen].min()), 3) if floor_pen.any() else 0.0,
               "support_penetration_frames": int(sup_pen_any.sum()), "support_penetration_max_m": round(float(sup_depth.max()), 3),
               "supports": sup_out}
        (out / f"{name}.json").write_text(json.dumps(row, indent=1))
        rows.append(row)
        print(json.dumps({k: v for k, v in row.items() if k != "supports"} | {"supports": [
            {k: s[k] for k in ("height_m", "frames_at_rest", "held_share", "status", "penetration_frames", "penetration_max_m", "moge")} for s in sup_out]}), flush=True)
    (out / "summary.json").write_text(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()
