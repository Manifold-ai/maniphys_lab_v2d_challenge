"""Support surfaces from Tier 3 signals, and object penetration of the floor and of those supports (Tier 3 inputs only).

Tier 3 may not read the released support_surface files (they sit where the clean object rests: a clean trajectory in
disguise, see the handoff), so the supports are measured here.

Static segments: every STATIC_WINDOW-frame window in the segment keeps the object's positions within STATIC_RADIUS_M of
the window's median. Only the object's motion is looked at: a hand usually stays by the object just before a pick and
after a place, and a speed threshold misses rest because CARI4D's pose jitters ~5 mm per frame (15 cm/s) while staying
within a few cm. A static segment whose lowest hull point is more than FLOOR_TOL_M above the floor is a candidate:
its median lowest point is the height, the hull's footprint at its median pose a patch.

Static and held look alike from the object's motion alone (a held object kept still in the air also reads as static),
so MoGe-2 on the people-free plate (t3_walls.py moge), turned onto the released floor as t3_walls.py does and moved by
camera_register.json for registered cameras, decides whether a surface is there: its horizontal points (normal within
MOGE_NORMAL_DEG of up) over the candidate's patch, below the object's bottom + MOGE_BAND_M, give the surface height
seen in the image. `support` when that surface is at most MOGE_ABOVE_M below the object's bottom; `above_surface` when
lower (held still above a table); `no_surface` when there is none (held still above the floor); the last two are
reported as rejected. MoGe also says which placements share a surface: `support` candidates whose MoGe surface heights
are within MERGE_DH_M and whose footprints are within MERGE_XY_M are one support (a mug picked up at A and set down at
B on one table). Its height is the object's (frame-weighted median of the placements' lowest points), not MoGe's:
one round table in six episodes reads 0.748-0.789 m from the objects, 0.775-0.845 m from MoGe. Each placement keeps
its own height and its offset from the support's (the error a post-process anchors away); the patch is the convex
hull of the footprints grown by PATCH_MARGIN_M, plus (10-16) where the object's centre of mass went while it slid or was
pushed across the surface, grown by SWEEP_MARGIN_M: frames whose lowest point stays within SWEEP_TOL_M of the support's
height (median-filtered as below) in a run that overlaps one of its placements, so the object never left the surface.
An object standing on a table has its centre of mass over the table, so this stays on the table; the footprints of those
frames did not (an iron pushed to the edge hangs over it, a book is slid half off before it is picked up; tried and
reverted 10-16). Rests alone covered only where the object paused: ep07's iron, ironed across a round table, was off its
patch whenever it was pushed past it. The height stays the rests'.

The hand: a segment held on at least HELD_ALL of its frames (physics check: a contact joint within HOLD_M) never saw the
hand leave, so resting and held in the hand cannot be told apart there. A support needs one placement that was not held
throughout; a support seen only through such held placements is dropped (`held_only`; ep28 10-13: a squeegee held still
over a bar stool's seat for 16 frames read as a 0.654 m support, while placements held throughout on a support that is
also seen unheld stay, ep03's mug and ep11's book). In a static segment that was not held throughout and has no surface
under it (`on_floor`), the frames no hand is at stand on the floor: nothing else holds the object up then, so its height
above the floor is reconstruction error (ep28's squeegee leaning on the stool after it is let go reads 14 cm off the
floor). Only those frames (`floor_runs`) are the floor's; the held ones may be in the air: a static segment can span a
lift of a few cm (ep24's watering can, lifted 8-11 cm and tipped for 566 frames between two rests on the floor, is one
static segment; anchoring all of it put the can, and the kneeling human with it, 8 cm too low, 10-13).
t3_height_post.py anchors the floor runs. Consecutive placements on one support between which the object's lowest point stays within LIFT_M of
the support (median-filtered over LIFT_FILTER frames, so one jittery frame does not count) are one placement: the object
never left the surface, its reconstruction drifted (ep25's final placement drifts 25 cm on the table under a resting
hand and read as two). Leaving downwards counts too (ep13's box goes from the desk to the floor and back).

Penetration, per frame, from the physics check's lowest hull point:
  floor     lowest point more than FLOOR_TOL_M below the floor (as object_floor_penetration);
  support   object centre over a `support` patch and lowest point between FLOOR_TOL_M and SUP_PEN_BAND_M below it;
            deeper is the object beside or under the table (lowered past the edge, pushed under a desk), not through it.

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
MOGE_ABOVE_M = 0.03
SUP_PEN_BAND_M = 0.15
LIFT_M = 0.05
LIFT_FILTER = 9
MERGE_DH_M = 0.03
MERGE_XY_M = 0.6
PATCH_MARGIN_M = 0.05
SWEEP_TOL_M = 0.02
SWEEP_MARGIN_M = 0.02
MOGE_NORMAL_DEG = 10.0
MOGE_MIN_H_M = 0.15
MOGE_BAND_M = 0.10
MOGE_MIN_POINTS = 200
HELD_ALL = 0.95


def basis(gp):
    n, d = np.asarray(gp[:3], float), float(gp[3])
    k = np.linalg.norm(n); n, d = n / k, d / k
    if d < 0:
        n, d = -n, -d
    u = np.array([1.0, 0, 0]) - n[0] * n; u /= np.linalg.norm(u)
    return n, d, -d * n, u, np.cross(n, u)


def static_segments(pos: np.ndarray) -> list[tuple[int, int]]:
    """[start, end) runs where every STATIC_WINDOW-frame window keeps the positions within STATIC_RADIUS_M of its median."""
    still = np.zeros(len(pos), bool)
    for i in range(len(pos) - STATIC_WINDOW + 1):
        w = pos[i:i + STATIC_WINDOW]
        if np.linalg.norm(w - np.median(w, 0), axis=1).max() < STATIC_RADIUS_M:
            still[i:i + STATIC_WINDOW] = True
    return [(int(a), int(b)) for a, b in zip(*[iter(np.flatnonzero(np.diff(np.r_[0, still.astype(int), 0])))] * 2)]


def main_basis(root: Path):
    """Floor-plane coordinates of the main camera's world, where registered cameras are moved to (as the patches)."""
    regs = json.loads((root / "runs/floor/camera_register.json").read_text())["groups"]
    _, _, o, u, v = basis(list(regs["1"]["plane"]["n"]) + [regs["1"]["plane"]["d"]])
    return o, u, v


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
    """Points within `margin` of a convex counter-clockwise polygon (signed edge distances).

    Repeated vertices are dropped first: a zero-length edge has no normal, its NaN distance fails every point, and the
    patches written to json (rounded to mm) have them (11 of 30 episodes, 10-13), so every reader of those files saw no
    point inside any patch, support clamps never fired downstream."""
    poly = np.asarray(poly, float)
    poly = poly[np.linalg.norm(np.roll(poly, -1, 0) - poly, axis=1) > 1e-9]
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
    from scipy.ndimage import median_filter
    from scipy.spatial.transform import Rotation

    root, version, phys, wdir, out = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3]), Path(sys.argv[4]), Path(sys.argv[5])
    out.mkdir(parents=True, exist_ok=True)
    metas = {m["episode_index"]: m for m in map(json.loads, (root / "input/meta/episodes_metadata.jsonl").read_text().splitlines()) if m}
    fit = json.loads((root / "runs/floor/floor_fit_f830.json").read_text())["episodes"]
    regs = json.loads((root / "runs/floor/camera_register.json").read_text())["groups"]
    o_m, u_m, v_m = main_basis(root)
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
        mesh = trimesh.load(root / "input" / m["mesh"], force="mesh")
        hull = np.asarray(mesh.convex_hull.vertices, np.float64)
        com_b = np.asarray((mesh if mesh.is_watertight else mesh.convex_hull).center_mass, np.float64)
        com = pos + rot @ com_b
        com_xy = np.c_[(com - o_m) @ u_m, (com - o_m) @ v_m]
        held = pz["held"]
        static = static_segments(pos)
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
            segs.append({"start": a, "end": b, "height_m": lo, "footprint": hull2(foot), "centre": xy[k],
                         "held_share": float(held[a:b].mean())})
        group = fit[name]["group"] if name in fit else 0
        mg = moge_world(wdir, name, gp, regs.get(str(group)))
        for sg in segs:  # MoGe decides only whether the object stands on a surface, and which surface
            cm = None
            if mg is not None:
                pts, hg = mg
                sel = inside(sg["footprint"], pts, PATCH_MARGIN_M + 0.10) & (hg > MOGE_MIN_H_M) & (hg < sg["height_m"] + MOGE_BAND_M)
                if sel.sum() >= MOGE_MIN_POINTS:
                    hist, edges = np.histogram(hg[sel], bins=np.arange(MOGE_MIN_H_M, sg["height_m"] + MOGE_BAND_M + 0.01, 0.01))
                    peak = float(edges[np.argmax(np.convolve(hist, np.ones(3) / 3, "same"))] + 0.005)
                    cm = {"points": int(sel.sum()), "surface_height_m": round(peak, 3), "minus_object_m": round(peak - sg["height_m"], 3)}
            sg["moge"] = cm
            sg["status"] = "no_surface" if cm is None else ("support" if cm["minus_object_m"] >= -MOGE_ABOVE_M else "above_surface")
            if sg["status"] == "no_surface" and sg["held_share"] < HELD_ALL:
                sg["status"] = "on_floor"
                e = np.flatnonzero(np.diff(np.r_[0, (~held[sg["start"]:sg["end"]].astype(bool)).astype(int), 0])) + sg["start"]
                sg["floor_runs"] = [[int(a), int(b)] for a, b in zip(e[::2], e[1::2], strict=True)]
        groups = []  # one per physical surface: MoGe surface heights within MERGE_DH_M, footprints within MERGE_XY_M
        for sg in sorted((g for g in segs if g["status"] == "support"), key=lambda g: -(g["end"] - g["start"])):
            for gr in groups:
                if any(abs(sg["moge"]["surface_height_m"] - o["moge"]["surface_height_m"]) <= MERGE_DH_M
                       and np.linalg.norm(sg["centre"] - o["centre"]) <= MERGE_XY_M for o in gr):
                    gr.append(sg); break
            else:
                groups.append([sg])
        for gr in groups:  # a support seen only through placements held throughout is not seen
            if all(g["held_share"] >= HELD_ALL for g in gr):
                for g in gr:
                    g["status"] = "held_only"
        groups = [gr for gr in groups if gr[0]["status"] == "support"]
        sup_out = []
        floor_pen = obj_low < -FLOOR_TOL_M
        sup_pen_any = np.zeros(len(obj_low), bool); sup_depth = np.zeros(len(obj_low))
        for i, gr in enumerate(groups):
            gr.sort(key=lambda g: g["start"])
            frames = np.concatenate([np.arange(g["start"], g["end"]) for g in gr])
            h = float(np.median(obj_low[frames]))  # the support's height is the object's
            low_f = median_filter(obj_low, LIFT_FILTER, mode="nearest")
            merged = [dict(gr[0], parts=[gr[0]])]
            for g in gr[1:]:
                prev = merged[-1]
                if np.all(np.abs(low_f[prev["end"]:g["start"]] - h) <= LIFT_M):  # never left the surface in between
                    prev["parts"].append(g); prev["end"] = g["end"]
                else:
                    merged.append(dict(g, parts=[g]))
            for mp in merged:
                fr = np.concatenate([np.arange(q["start"], q["end"]) for q in mp["parts"]])
                mp["height_m"] = float(np.median(obj_low[fr]))
                mp["centre"] = np.median(np.stack([q["centre"] for q in mp["parts"]]), 0)
                mp["drift_m"] = float(max(np.linalg.norm(q["centre"] - r["centre"]) for q in mp["parts"] for r in mp["parts"]))
                mp["static_frames"] = int(len(fr))
            rest_poly = hull2(np.concatenate([g["footprint"] for g in gr]))
            on = np.abs(low_f - h) <= SWEEP_TOL_M
            e = np.flatnonzero(np.diff(np.r_[0, on.astype(int), 0]))
            fset = set(frames.tolist())
            sweep = [f for a, b in zip(e[::2], e[1::2], strict=True) if any(t in fset for t in range(a, b)) for f in range(a, b)]
            ring = SWEEP_MARGIN_M * np.c_[np.cos(np.arange(8) * np.pi / 4), np.sin(np.arange(8) * np.pi / 4)]
            swept = (com_xy[sweep][:, None] + ring[None]).reshape(-1, 2) if sweep else np.zeros((0, 2))
            poly = hull2(np.concatenate([rest_poly, swept]))
            area = lambda P: float(0.5 * abs(np.dot(P[:, 0], np.roll(P[:, 1], 1)) - np.dot(P[:, 1], np.roll(P[:, 0], 1)))) if len(P) >= 3 else 0.0
            over = inside(poly, xy, PATCH_MARGIN_M)
            pen = over & (obj_low < h - FLOOR_TOL_M) & (obj_low > h - SUP_PEN_BAND_M)
            sup_pen_any |= pen; sup_depth = np.maximum(sup_depth, np.where(pen, h - obj_low, 0))
            sup_out.append({"support": i, "height_m": round(h, 3), "frames_at_rest": int(len(frames)),
                            "moge_surface_heights_m": [g["moge"]["surface_height_m"] for g in gr],
                            "placements": [{"start": g["start"], "end": g["end"], "static_frames": g["static_frames"],
                                            "height_m": round(g["height_m"], 3), "offset_m": round(g["height_m"] - h, 3),
                                            "centre_xy_m": np.round(g["centre"], 3).tolist(), "drift_m": round(g["drift_m"], 3),
                                            "held_share": round(float(held[g["start"]:g["end"]].mean()), 2)} for g in merged],
                            "patch_area_m2": round(area(poly), 3), "rest_patch_area_m2": round(area(rest_poly), 3),
                            "sweep_frames": len(sweep),
                            "patch_xy_m": poly.round(3).tolist(), "penetration_frames": int(pen.sum()),
                            "penetration_max_m": round(float((h - obj_low)[pen].max()), 3) if pen.any() else 0.0})
        rejected = [{"start": g["start"], "end": g["end"], "height_m": round(g["height_m"], 3), "status": g["status"],
                     "centre_xy_m": np.round(g["centre"], 3).tolist(), "held_share": round(float(held[g["start"]:g["end"]].mean()), 2),
                     "moge": g["moge"]} | ({"floor_runs": g["floor_runs"]} if "floor_runs" in g else {})
                    for g in sorted(segs, key=lambda g: g["start"]) if g["status"] != "support"]
        row = {"episode": name, "tier": rep["tier"], "frames": len(obj_low), "group": group, "rest_frames": rest_on,
               "floor_penetration_frames": int(floor_pen.sum()), "floor_penetration_max_m": round(float(-obj_low[floor_pen].min()), 3) if floor_pen.any() else 0.0,
               "support_penetration_frames": int(sup_pen_any.sum()), "support_penetration_max_m": round(float(sup_depth.max()), 3),
               "supports": sup_out, "rejected": rejected}
        (out / f"{name}.json").write_text(json.dumps(row, indent=1))
        rows.append(row)
        print(json.dumps({k: v for k, v in row.items() if k not in ("supports", "rejected")} | {"supports": [
            {k: sp[k] for k in ("height_m", "frames_at_rest", "penetration_frames", "penetration_max_m")} | {"placements": len(sp["placements"])}
            for sp in sup_out], "rejected": len(rejected)}), flush=True)
    (out / "summary.json").write_text(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()
