"""Object rest correction along the viewing ray, depth change capped, the rest vertical (Tier 3 inputs only).

A resting object's lowest hull point must lie on its surface: a condition along the floor normal. Monocular
reconstruction knows an object's direction from the camera better than its distance, and the silhouette is the
observation: moving the object along its own ray keeps it there, any move across the ray takes it off. So the condition
is met by a depth ratio k about the camera centre (every point along its own ray), within 1 +- K_CAP; only what the cap
leaves is made up by a vertical shift. Depth errors are ~1.7 % of the distance (rest frames 1-3 % per episode,
t3_depth_diag.py; held frames on the floor 5.3 cm rms at ~3 m, t3_hand_depth_diag.py), so K_CAP is about 3 of them.
The cap is for tables: the ray from a 1.39 m camera to a table top is nearly level, a move along it changes the height
little, and an uncapped ray fix of a few cm of height took 10-48 cm of depth (ep27, 10-13).

History (10-13, silhouette IoU against the SAM2 mask, 29 episodes): a vertical shift (t3_height_post.py) 0.810 -> 0.737;
a ray fix 0.808 but implausible depths on tables; a split weighted by assumed errors (2 cm across the ray) 0.764; the same
with one height per rest segment and k-only interpolation 0.792, the rest of its drop on floor-clamped and rest frames,
the ones still moved across the ray. Wherever the object sat on its silhouette, moving it across the ray made it worse.

  anchors   rest frames whose surface is known, as t3_height_post.py: floor static segments (median lowest hull point
            within FLOOR_TOL_M), t3_support's `on_floor` floor runs, support placements. One correction per segment: k is
            the median over its frames of the k that puts the lowest point on the surface, capped; what the capped k
            leaves (median over the segment) is a vertical shift, which fades to 0 over RAMP frames outside the segment.
            Within a rest the lowest point wanders ~1 cm, from the position estimate, not the orientation
            (t3_rest_split.py), and is left alone.
  between   k interpolated in frame index between anchored frames (the nearest outside), along each frame's own ray, so
            frames between rests keep their image position (interpolating a rest's 3-D move instead put it partly
            across the new ray: held interpolated frames lost 0.09-0.23 IoU on ep02/04/09/25/27). Held frames keep the
            object's own depth: the hand pins it only within ~29 cm against the object's own ~5 cm error
            (t3_hand_depth_diag.py), so the hand does not set it; held frames whose object moves more than HAND_REACH_M
            plus its hand distance are reported.
  clamp     no lowest point below the floor, none within SUP_PEN_BAND_M below a support over its patch (t3_support's
            band rule): the raise each frame needs is smoothed in time off rests (clamp_raise: never below the need,
            rest frames exactly their own), then made up by k first, within the cap, then vertically.
  human     --move-human (vertical, the default) or --move-human=3d: on held frames the human root follows the object's
            vertical move, or all of it (ramped and smoothed as t3_height_post.py); either way not down past the feet: the
            vertical part is cut so the lower sole goes no lower than the floor, or than it already was (10-13, user: a
            human standing or kneeling on the floor is right where the object's correction is interpolated; the rest is
            the robot's leg IK). Vertical only since 10-13: following the depth part too moved humans 16-18 cm (p95) back
            and forth on ep02/10/14/16 for a depth correction that is the object's own (the human's depth is estimated
            apart, its feet on the floor) and lifted feet (feet_floating 1226 -> 1464 frames, best_hm -> best_dr2); the
            hand-object gap that leaves along the ray is the robot arm's to absorb. best_dr2 was made with 3d.
Frames whose centre is above the camera height have no ray fix (k does not raise them); they get vertical only.

The camera centre in the world is the world step's similarity (fitted from the episode's object_cam_focal / object_world
pair in its convert dir, from the selection json; its residual is reported).

    python t3_depth_post.py <tier3 root> <version> <selection json> <support dir> <physics dir> <out version> [--move-human[=3d]]
        [k_cap=<x>] [only=<ep>,<ep>] [dump=<dir>] [ep=convert dir ...]
dump writes per frame where each episode's correction came from (anchored, interpolated, floor or support clamp) for
t3_align_check.py split=. Writes runs/<out version>{,_suspect}/ and runs/<out version>.depth_post.json.
"""

from __future__ import annotations

import json
import sys
from itertools import pairwise
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import t3_inputs  # noqa: E402
from t3_height_post import CV_TO_SOMA, HUMAN_SIGMA, held_weight, quat_wxyz_to_mat, shifts  # noqa: E402
from t3_support import FLOOR_TOL_M, PATCH_MARGIN_M, SUP_PEN_BAND_M, basis, inside, main_basis, static_segments  # noqa: E402

K_CAP = 0.05
HAND_REACH_M = 0.15
RAMP = 10  # frames
CLAMP_HALF = 5  # frames


def similarity(conv: Path):
    c = np.load(conv / "object_cam_focal.npz")["T_cam_glb"][:, :3, 3]
    w = np.load(conv / "object_world.npz")["T_world_glb"][:, :3, 3]
    mc, mw = c.mean(0), w.mean(0)
    u, sv, vt = np.linalg.svd((w - mw).T @ (c - mc))
    dd = np.diag([1, 1, np.sign(np.linalg.det(u @ vt))])
    r = u @ dd @ vt
    s = np.trace(np.diag(sv) @ dd) / ((c - mc) ** 2).sum()
    t = mw - s * r @ mc
    return t, float(np.abs((c @ r.T) * s + t - w).max())


def k_for(h, v, low, c_rel, below):
    """Per frame, the depth ratio putting the lowest point at height h given a vertical shift v (inf where no ray fix).

    The object's position moves to cam + k (pos - cam), its shape unchanged, so its lowest point rises by
    (k - 1) * c_rel, c_rel the centre's height relative to the camera (10-13: the first ray fix used the lowest point's
    height relative to the camera, the formula for scaling the whole object about the camera, and missed by 10-25 %)."""
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(below, 1.0 + (h - v - low) / c_rel, np.inf)


def smooth_raise(need: np.ndarray) -> np.ndarray:
    """A raise no smaller than need on any frame, continuous in time: max over CLAMP_HALF frames each side, then the mean
    over the same window (each frame's window holds only maxima at least its own need). Raising frame by frame switched
    on and off between neighbours and jumped the object: ep19 816-830 went 0 -> 12-15 cm -> 0 cm in one frame (10-13)."""
    from scipy.ndimage import maximum_filter1d, uniform_filter1d
    w = 2 * CLAMP_HALF + 1
    return uniform_filter1d(maximum_filter1d(need, w, mode="nearest"), w, mode="nearest")


def clamp_raise(need: np.ndarray, anchored: np.ndarray) -> np.ndarray:
    """Smoothed on frames off rest only; rest frames get exactly their own need. A rest's lowest point wanders ~1 cm about
    its surface, half its frames just under it; smoothing there lifted whole rests by the local maximum (up to 4.8 cm
    off their surface, 10-13), while the jumps it is for are on carried and dragged frames."""
    return np.where(anchored, need, smooth_raise(np.where(anchored, 0.0, need)))


def apply_raise(r, k, vert, c_rel, below, k_cap) -> None:
    """In place: raise the lowest point by r per frame, by k first (within the cap), the rest by the vertical shift."""
    with np.errstate(divide="ignore", invalid="ignore"):
        k_new = np.where(below & (r > 0), np.maximum(k + r / c_rel, 1 - k_cap), k)  # c_rel < 0: a smaller k raises
    k_new = np.minimum(k_new, k)
    rise = np.where(below, (k_new - k) * c_rel, 0.0)
    k[:] = k_new
    vert += np.maximum(0.0, r - rise)


def main() -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq
    import trimesh
    from scipy.ndimage import gaussian_filter1d

    human_mode = next((a.split("=", 1)[1] if "=" in a else "vertical" for a in sys.argv[1:] if a.startswith("--move-human")), None)
    if human_mode not in (None, "vertical", "3d"):
        raise SystemExit(f"--move-human={human_mode}: vertical or 3d")
    move_human = human_mode is not None
    kv = dict(a.split("=", 1) for a in sys.argv[1:] if "=" in a and not a.startswith("--"))
    k_cap = float(kv.pop("k_cap", K_CAP))
    only = {int(x) for x in kv.pop("only", "").split(",") if x}
    dump = Path(kv.pop("dump")) if "dump" in kv else None
    rest = [a for a in sys.argv[1:] if not a.startswith("--move-human") and "=" not in a]
    root, version, sel, sup_dir, phys, out_v = Path(rest[0]), rest[1], Path(rest[2]), Path(rest[3]), Path(rest[4]), rest[5]
    runs = root / "runs"
    if (runs / out_v).exists() or (runs / f"{out_v}_suspect").exists():
        raise SystemExit(f"runs/{out_v} exists; pick a new name")
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "libs" / "v2d_infra"))
    from tier_guard import forbid_lower_tiers
    forbid_lower_tiers()  # Tier 3: nothing from Tier 1 or Tier 2 (Kaggle 2.8.c)
    import t3_provenance  # 10-16: record the code and inputs, as the other post-processes
    prov = t3_provenance.stamp([root / "input", runs / version, runs / f"{version}_suspect", sel, sup_dir, phys])
    metas = {m["episode_index"]: m for m in map(json.loads, (root / "input/meta/episodes_metadata.jsonl").read_text().splitlines()) if m}
    convs = {r["episode"]: kv.get(r["episode"], r["convert"]) for r in json.loads(sel.read_text())}
    o_m, u_m, v_m = main_basis(root)
    report = []
    for src_v, dst_v in ((version, out_v), (f"{version}_suspect", f"{out_v}_suspect")):
        for f in sorted((runs / src_v / "data" / "chunk-000").glob("episode_*.parquet")):
            table = pq.read_table(f)
            ep = int(table.column("episode_index")[0].as_py())
            if only and ep not in only:
                continue
            m = metas[ep]
            name = f"ep{ep:02d}_{m['object']}"
            cam, fit_res = similarity(runs / convs[name] / name)
            n_up, d_up, _, _, _ = basis(t3_inputs.ground_plane(root, m))
            pose = np.stack(table.column("observation.object.pose").to_numpy(zero_copy_only=False)).astype(np.float64)
            pos, rot = pose[:, :3], quat_wxyz_to_mat(pose[:, 3:7])
            hull = np.asarray(trimesh.load(root / "input" / m["mesh"], force="mesh").convex_hull.vertices, np.float64)
            low = ((np.einsum("fij,kj->fki", rot, hull) + pos[:, None]) @ n_up + d_up).min(1)
            nf = len(pos)

            anchors = []
            for a, b in static_segments(pos):
                if float(np.median(low[a:b])) <= FLOOR_TOL_M:
                    anchors.append((a, b, 0.0, "floor"))
            sj = json.loads((sup_dir / f"{name}.json").read_text()) if (sup_dir / f"{name}.json").exists() else {}
            sup = sj.get("supports", [])
            for r in sj.get("rejected", []):
                if r["status"] == "on_floor":
                    anchors += [(a, b, 0.0, "floor") for a, b in r["floor_runs"]]
            for s in sup:
                for p in s["placements"]:
                    anchors.append((p["start"], p["end"], float(s["height_m"]), "support"))
            anchors.sort()
            for (_, b1, _, _), (a2, _, _, _) in pairwise(anchors):
                if a2 < b1:
                    raise SystemExit(f"{name}: anchors overlap at {a2}..{b1}")
            ray = pos - cam
            c_rel = ray @ n_up                                 # the centre's height relative to the camera
            below = c_rel < -1e-6                              # centre under the camera: k raises or lowers it

            k_target = np.full(nf, np.nan)                     # depth ratio - 1 on anchored frames
            vert = np.zeros(nf)                                # vertical shift: what the capped k leaves, on rests, ramped out
            edges = []
            for a, b, h, _ in anchors:
                kk = k_for(h, 0.0, low, c_rel, below)[a:b]
                k_seg = float(np.clip(np.median(kk[np.isfinite(kk)]), 1 - k_cap, 1 + k_cap)) if np.isfinite(kk).any() else 1.0
                k_target[a:b] = k_seg - 1.0
                v_seg = float(np.median(h - (low[a:b] + np.where(below[a:b], k_seg - 1.0, 0.0) * c_rel[a:b])))
                vert[a:b] = v_seg
                edges.append((a, b, v_seg))
            anchored = ~np.isnan(k_target)
            for a, b, v_seg in edges:
                for i in range(1, RAMP + 1):
                    w = 1.0 - i / (RAMP + 1)
                    for fr in (a - i, b - 1 + i):
                        if 0 <= fr < nf and not anchored[fr]:
                            vert[fr] += w * v_seg
            k = 1.0 + shifts(k_target)
            k = np.where(below, k, 1.0)
            delta_interp = (k[:, None] - 1.0) * ray + vert[:, None] * n_up

            now = low + (k - 1.0) * c_rel + vert
            floor_clamped = now < 0.0
            apply_raise(clamp_raise(np.maximum(0.0, -now), anchored), k, vert, c_rel, below, k_cap)
            sup_clamped = np.zeros(nf, bool)
            for s in sup:
                poly = np.asarray(s["patch_xy_m"], np.float64)
                if len(poly) < 3:
                    continue
                h = s["height_m"]
                p_now = cam + k[:, None] * ray + vert[:, None] * n_up
                xy = np.c_[(p_now - o_m) @ u_m, (p_now - o_m) @ v_m]
                now = low + (k - 1.0) * c_rel + vert
                pen = inside(poly, xy, PATCH_MARGIN_M) & (now < h) & (now > h - SUP_PEN_BAND_M)
                apply_raise(clamp_raise(np.where(pen, h - now, 0.0), anchored), k, vert, c_rel, below, k_cap)
                sup_clamped |= pen
            delta = (k[:, None] - 1.0) * ray + vert[:, None] * n_up

            new = pose.copy()
            new[:, :3] = pos + delta
            i = table.schema.get_field_index("observation.object.pose")
            out_t = table.set_column(i, table.schema.field(i), pa.FixedSizeListArray.from_arrays(pa.array(new.astype(np.float32).ravel(), pa.float32()), 7))

            pz = np.load(phys / "out" / f"{name}.npz")
            held = pz["held"].astype(bool)
            if dump is not None:
                dump.mkdir(parents=True, exist_ok=True)
                np.savez(dump / f"{name}.npz", anchored=anchored, floor_clamped=floor_clamped, support_clamped=sup_clamped,
                         delta_interp=delta_interp, delta=delta, k=k, vert=vert, held=held)
            hdisp, cut = np.zeros((nf, 3)), np.zeros(nf, bool)
            if move_human:
                follow = delta if human_mode == "3d" else (delta @ n_up)[:, None] * n_up
                hdisp = gaussian_filter1d(held_weight(held)[:, None] * follow, HUMAN_SIGMA, axis=0, mode="nearest")
                dz = hdisp @ n_up
                floor_dz = -np.maximum(pz["feet"], 0.0)
                cut = (dz < 0) & (dz < floor_dz)
                hdisp[cut] += (floor_dz - dz)[cut][:, None] * n_up
                tr = np.stack(table.column("observation.human.translation").to_numpy(zero_copy_only=False)).astype(np.float64)
                j = out_t.schema.get_field_index("observation.human.translation")
                out_t = out_t.set_column(j, out_t.schema.field(j), pa.FixedSizeListArray.from_arrays(
                    pa.array((tr + hdisp @ CV_TO_SOMA).astype(np.float32).ravel(), pa.float32()), 3))
            md = dict(out_t.schema.metadata or {})
            md[b"depth_post"] = json.dumps({"from": version, "anchors": len(anchors), "move_human": human_mode,
                                            "k_cap": k_cap}).encode()
            out_t = out_t.replace_schema_metadata(md)
            dst = runs / dst_v / "data" / "chunk-000" / f.name
            dst.parent.mkdir(parents=True, exist_ok=True)
            pq.write_table(out_t, dst)
            (runs / dst_v / "meta").mkdir(exist_ok=True)
            mf = runs / src_v / "meta" / f"episode_{ep:06d}.metadata.json"
            (runs / dst_v / "meta" / mf.name).write_bytes(mf.read_bytes())

            r4 = lambda x: round(float(x), 4)
            dn = np.linalg.norm(delta, axis=1)
            vert = delta @ n_up
            horiz = np.linalg.norm(delta - vert[:, None] * n_up, axis=1)
            ray = (pos - cam) / np.linalg.norm(pos - cam, axis=1, keepdims=True)
            along = np.abs((delta * ray).sum(1))
            row = {"episode": name, "tier": dst_v, "frames": nf, "convert": convs[name], "similarity_fit_m": r4(fit_res),
                   "anchors": [{"start": a, "end": b, "kind": kd, "surface_m": r4(h)} for a, b, h, kd in anchors],
                   "move_m_p50_p95_max": [r4(np.median(dn)), r4(np.percentile(dn, 95)), r4(dn.max())],
                   "vertical_m_p50_p95": [r4(np.median(np.abs(vert))), r4(np.percentile(np.abs(vert), 95))],
                   "horizontal_m_p50_p95": [r4(np.median(horiz)), r4(np.percentile(horiz, 95))],
                   "along_ray_share_p50": r4(np.median(along[dn > 1e-4] / dn[dn > 1e-4])) if (dn > 1e-4).any() else None,
                   "floor_clamped_frames": int(floor_clamped.sum()), "support_clamped_frames": int(sup_clamped.sum()),
                   "k_capped_frames": int((np.abs(k - 1.0) >= k_cap - 1e-9).sum()),
                   "below_floor_after": int((low + delta @ n_up < -1e-6).sum())}
            if held.any():
                row["held_beyond_reach_frames"] = int((held & (pz["hand_d"] + dn > HAND_REACH_M)).sum())
            if move_human:
                hn = np.linalg.norm(hdisp, axis=1)
                row["human_move_m_p50_p95_max"] = [r4(np.median(hn)), r4(np.percentile(hn, 95)), r4(hn.max())]
                row["human_feet_cut_frames"] = int(cut.sum())
            report.append(row)
            print(json.dumps({kk: v for kk, v in row.items() if kk != "anchors"} | {"anchors": len(anchors)}), flush=True)
    (runs / f"{out_v}.depth_post.json").write_text(json.dumps(report, indent=1))
    t3_provenance.write(runs / f"{out_v}.provenance.json", prov | {"made_by": "t3_depth_post.py", "from_version": version,
                                                                     "supports": str(sup_dir), "move_human": human_mode})


if __name__ == "__main__":
    main()
