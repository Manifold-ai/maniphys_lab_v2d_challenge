"""Where the object's height error comes from: depth along the viewing ray vs offset across it (diagnosis, CPU).

On a frame where the object rests unheld on a known surface (the floor: a static segment whose median lowest point is
within FLOOR_TOL_M of the floor, or t3_support's `on_floor` runs; a support: its placements), its lowest point must lie
on that surface. Monocular reconstruction knows the object's direction from the camera far better than its distance, so
that one condition is read as a depth error: the factor k that scales the object about the camera centre (every vertex
along its own ray, the image unchanged) until its lowest point is on the surface. The vertical shift t3_height_post.py
applies instead is reported next to it, and the horizontal move the same k would make (what a vertical-only fix leaves).
Across the ray: the silhouette centroid offset from the track check (pixels, magnitude), in cm at the object's depth.
Cross-check of the depth: object_check.json's silhouette depth factor on the same frames, where it was computed.

The camera centre in the world is the world step's similarity (fitted from the episode's object_cam_focal /
object_world pair: p_w = s R p_c + t, so the centre is t); k is the same in the camera frame.

    python t3_depth_diag.py <tier3 root> <selection json> <support dir> <physics dir> <out json> [ep=convert dir ...]
Per episode: rest frames used, k (median, p10-p90, spread within and between segments), vertical shift, the horizontal
move left by a vertical-only fix, centroid offset (cm), silhouette depth factor; and a summary over episodes.
"""

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import t3_inputs  # noqa: E402
from t3_support import FLOOR_TOL_M, basis, static_segments  # noqa: E402

TRACK = {"convert": "track_check", "convert_v2": "track_check_v2sel", "convert_fp": "track_check_fp"}
CHECK = {"convert": "checks", "convert_v2": "checks_v2", "convert_fp": "checks_fp"}


def similarity(conv: Path):
    c = np.load(conv / "object_cam_focal.npz")
    tw = np.load(conv / "object_world.npz")["T_world_glb"]
    pc, pw = c["T_cam_glb"][:, :3, 3], tw[:, :3, 3]
    mc, mw = pc.mean(0), pw.mean(0)
    u, sv, vt = np.linalg.svd((pw - mw).T @ (pc - mc))
    dd = np.diag([1, 1, np.sign(np.linalg.det(u @ vt))])
    r = u @ dd @ vt
    s = np.trace(np.diag(sv) @ dd) / ((pc - mc) ** 2).sum()
    t = mw - s * r @ mc
    res = np.abs((pc @ r.T) * s + t - pw).max()
    return s, t, tw, c["intrinsics"], res


def main() -> None:
    import trimesh

    root, sel, sup_dir, phys, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]), Path(sys.argv[5])
    over = dict(x.split("=", 1) for x in sys.argv[6:])
    metas = {m["episode_index"]: m for m in map(json.loads, (root / "input/meta/episodes_metadata.jsonl").read_text().splitlines()) if m}
    rows = []
    for r in json.loads(sel.read_text()):
        ep, name = r["episode_index"], r["episode"]
        conv = over.get(name, r["convert"])
        m = metas[ep]
        s, cam, tw, K, res = similarity(root / "runs" / conv / name)
        n, d, _, _, _ = basis(t3_inputs.ground_plane(root, m))
        hull = np.asarray(trimesh.load(root / "input" / m["mesh"], force="mesh").convex_hull.vertices, np.float64)
        rot, pos = tw[:, :3, :3], tw[:, :3, 3]
        verts = np.einsum("fij,kj->fki", rot, hull) + pos[:, None]
        low = verts @ n + d
        z = np.load(phys / "out" / f"{name}.npz")
        held = z["held"].astype(bool)
        sj = json.loads((sup_dir / f"{name}.json").read_text())
        surf = np.full(len(pos), np.nan)  # the surface height each unheld rest frame stands on
        seg_id = np.full(len(pos), -1)
        segs = [(a, b, 0.0) for a, b in static_segments(pos) if np.median(low.min(1)[a:b]) <= FLOOR_TOL_M]
        segs += [(a, b, 0.0) for q in sj["rejected"] if q["status"] == "on_floor" for a, b in q["floor_runs"]]
        segs += [(p["start"], p["end"], float(sp["height_m"])) for sp in sj["supports"] for p in sp["placements"]]
        for i, (a, b, h) in enumerate(segs):
            surf[a:b] = h
            seg_id[a:b] = i
        use = ~np.isnan(surf) & ~held
        if use.sum() < 5:
            rows.append({"episode": name, "convert": conv, "rest_frames": int(use.sum())})
            print(json.dumps(rows[-1]), flush=True)
            continue
        f = np.flatnonzero(use)
        hc = cam @ n + d                                   # camera height above the floor
        a_min = ((verts[f] - cam) @ n).min(1)               # lowest vertex relative to the camera, along the normal
        k = (surf[f] - hc) / a_min                          # scale about the camera that puts it on the surface
        dz = surf[f] - low[f].min(1)                        # t3_height_post's vertical shift
        ctr = verts[f].mean(1) - cam
        horiz = ctr - (ctr @ n)[:, None] * n
        hmove = np.abs(k - 1) * np.linalg.norm(horiz, axis=1)  # horizontal move of a ray fix, left by a vertical fix
        depth = np.linalg.norm(ctr, axis=1)
        trk = root / "runs" / TRACK[conv] / f"{name}.npz" if conv in TRACK else root / "runs" / conv / name / "track_check.npz"
        cpx = np.load(trk)["centroid_px"][f]
        perp_cm = cpx * depth / K[0, 0] * 100                # px at the object depth (the world scale cancels), in cm
        sil = {}
        chk = root / "runs" / CHECK.get(conv, "-") / name / "object_check.json"  # checks of this version's own poses only
        if chk.exists():
            sil = {q["frame"]: q["depth_factor"] for q in json.loads(chk.read_text())["rows"] if q.get("depth_factor") is not None}
        both = [(kk, sil[fr]) for kk, fr in zip(k, f) if fr in sil]
        per_seg = [float(np.median(k[seg_id[f] == i])) for i in np.unique(seg_id[f])]
        within = float(np.median([np.std(k[seg_id[f] == i]) for i in np.unique(seg_id[f]) if (seg_id[f] == i).sum() >= 5] or [np.nan]))
        q = lambda x: [round(float(v), 4) for v in np.nanpercentile(x, [10, 50, 90])]
        row = {"episode": name, "convert": conv, "world_scale": round(float(s), 4), "similarity_fit_m": round(float(res), 5),
               "rest_frames": int(len(f)), "segments": len(per_seg), "camera_height_m": round(float(hc), 3),
               "k_p10_p50_p90": q(k), "k_per_segment": [round(x, 4) for x in per_seg],
               "k_std_within_segment": round(within, 4), "k_spread_between_segments": round(float(np.ptp(per_seg)), 4),
               "vertical_shift_m_p10_p50_p90": q(dz), "horizontal_left_m_p10_p50_p90": q(hmove),
               "depth_m_p50": round(float(np.median(depth)), 3), "centroid_offset_cm_p10_p50_p90": q(perp_cm[~np.isnan(perp_cm)]) if (~np.isnan(perp_cm)).any() else None,
               "silhouette_depth_factor_vs_k": {"frames": len(both), "corr": round(float(np.corrcoef(np.array(both).T)[0, 1]), 3) if len(both) > 5 else None,
                                                "sil_p50": round(float(np.median([b for _, b in both])), 4) if both else None,
                                                "k_p50": round(float(np.median([a for a, _ in both])), 4) if both else None}}
        rows.append(row)
        print(json.dumps(row), flush=True)
    ok = [x for x in rows if "k_p10_p50_p90" in x]
    med = np.array([x["k_p10_p50_p90"][1] for x in ok])
    summary = {"episodes_with_rests": len(ok), "episode_median_k_p10_p50_p90": [round(float(v), 4) for v in np.percentile(med, [10, 50, 90])],
               "between_episodes_std": round(float(np.std(med)), 4),
               "within_segment_std_median": round(float(np.nanmedian([x["k_std_within_segment"] for x in ok])), 4),
               "between_segments_spread_median": round(float(np.median([x["k_spread_between_segments"] for x in ok if x["segments"] > 1] or [np.nan])), 4)}
    print(json.dumps(summary))
    out.write_text(json.dumps({"summary": summary, "episodes": rows}, indent=1))


if __name__ == "__main__":
    main()
