"""Object height post-process: resting placements onto their surface, then no penetration (Tier 3 inputs only).

Only heights change (shifts along the released floor's normal); horizontal positions and orientations are untouched.
The object is shifted per episode as below; the human is untouched unless --move-human (then see "human"). Per episode:

  anchors   a resting placement's height is known: on the floor (a t3_support static segment whose median lowest hull
            point is within FLOOR_TOL_M of the floor or below it; and in a segment t3_support marks `on_floor`, the
            frames no hand is at) the lowest point goes to 0; on a support (t3_support's
            placements) to the support's height, frame by frame: a resting object touches its surface on every
            frame, so its height jitter at rest goes too (10-13: one shift per placement left the lowest point up to
            10 cm off the floor within a rest, ep14 / ep18 / ep28).
  between   frames between two placements (carried, pushed) get the shift interpolated linearly in frame index from
            the neighbouring placements' end and start frames; before the first and after the last placement the
            nearest placement frame's shift.
  clamp     no frame's lowest point below the floor; over a support patch (t3_support's, grown by its PATCH_MARGIN_M),
            none within SUP_PEN_BAND_M below the support (deeper is beside or under it, see t3_support.py).

  human     --move-human: the human root translation gets the object's shift on held frames (physics check of <version>:
            a contact joint within HOLD_M), so hand and object keep their vertical relation; off held frames it ramps to 0
            over HUMAN_RAMP frames on each side (held mask grown by HUMAN_RAMP, then a box average of 2 HUMAN_RAMP + 1),
            then a Gaussian of HUMAN_SIGMA frames: the object's shift has one-frame spikes (ep19's probe seam, ep28's pose
            jumps: 0.2 m in a frame), which the body must not follow. Held frames keep a residual hand-object height
            change (reported). Feet then leave or enter the floor by that shift; the robot's leg IK takes that up
            (10-13, user and rxzhou: the retarget levels human and object together onto the floor plane, mismatched feet
            are the robot foot IK's job).

Supports come from t3_support.py on the same version, never from the released support_surface files.
Held frames are reported with the object's shift and the human's, so the change in hand-object height is their difference.

    python t3_height_post.py <tier3 root> <version> <support dir> <physics dir> <out version> [--move-human]
Writes runs/<out version>{,_suspect}/ (same split as the input) and runs/<out version>.height_post.json.
"""

from __future__ import annotations

import json
import sys
from itertools import pairwise
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import t3_inputs  # noqa: E402
from t3_support import FLOOR_TOL_M, PATCH_MARGIN_M, SUP_PEN_BAND_M, basis, inside, main_basis, static_segments  # noqa: E402


def quat_wxyz_to_mat(q: np.ndarray) -> np.ndarray:
    from scipy.spatial.transform import Rotation
    return Rotation.from_quat(np.c_[q[:, 1:4], q[:, 0:1]]).as_matrix()


HUMAN_RAMP = 10  # frames (1/3 s at 30 fps)
HUMAN_SIGMA = 5.0  # frames
CV_TO_SOMA = np.diag([1.0, -1.0, -1.0])  # = t3_world_probe.F; its own inverse


def held_weight(held: np.ndarray, ramp: int = HUMAN_RAMP) -> np.ndarray:
    """1 on held frames, falling linearly to 0 within 2 ramp frames outside them."""
    from scipy.ndimage import binary_dilation, uniform_filter1d
    if not held.any():
        return np.zeros(len(held))
    grown = binary_dilation(held, np.ones(2 * ramp + 1, bool))
    return np.where(held, 1.0, uniform_filter1d(grown.astype(np.float64), 2 * ramp + 1, mode="constant"))


def shifts(target: np.ndarray) -> np.ndarray:
    """Per-frame shift: the anchored frames' own values (target, NaN elsewhere), linear in between, nearest outside."""
    known = np.flatnonzero(~np.isnan(target))
    if not len(known):
        return np.zeros(len(target))
    return np.interp(np.arange(len(target)), known, target[known])


def main() -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq
    import trimesh

    argv = [a for a in sys.argv[1:] if a != "--move-human"]
    move_human = len(argv) < len(sys.argv) - 1
    root, version, sup_dir, phys, out_v = Path(argv[0]), argv[1], Path(argv[2]), Path(argv[3]), argv[4]
    runs = root / "runs"
    if (runs / out_v).exists() or (runs / f"{out_v}_suspect").exists():
        raise SystemExit(f"runs/{out_v} exists; pick a new name")
    metas = {m["episode_index"]: m for m in map(json.loads, (root / "input/meta/episodes_metadata.jsonl").read_text().splitlines()) if m}
    o_m, u_m, v_m = main_basis(root)
    report = []
    for src_v, dst_v in ((version, out_v), (f"{version}_suspect", f"{out_v}_suspect")):
        for f in sorted((runs / src_v / "data" / "chunk-000").glob("episode_*.parquet")):
            table = pq.read_table(f)
            ep = int(table.column("episode_index")[0].as_py())
            m = metas[ep]
            name = f"ep{ep:02d}_{m['object']}"
            n_up, d_up, _, _, _ = basis(t3_inputs.ground_plane(root, m))
            pose = np.stack(table.column("observation.object.pose").to_numpy(zero_copy_only=False)).astype(np.float64)
            pos, rot = pose[:, :3], quat_wxyz_to_mat(pose[:, 3:7])
            hull = np.asarray(trimesh.load(root / "input" / m["mesh"], force="mesh").convex_hull.vertices, np.float64)
            low = (np.einsum("fij,kj->fki", rot, hull) + pos[:, None]) @ n_up + d_up
            obj_low = low.min(1)
            nf = len(pos)

            anchors = []  # (start, end, surface height above the floor, kind)
            for a, b in static_segments(pos):
                if float(np.median(obj_low[a:b])) <= FLOOR_TOL_M:
                    anchors.append((a, b, 0.0, "floor"))
            sj = json.loads((sup_dir / f"{name}.json").read_text()) if (sup_dir / f"{name}.json").exists() else {}
            sup = sj.get("supports", [])
            for r in sj.get("rejected", []):  # its frames no hand is at stand on the floor (t3_support.py, on_floor)
                if r["status"] == "on_floor":
                    anchors += [(a, b, 0.0, "floor") for a, b in r["floor_runs"]]
            for s in sup:
                for p in s["placements"]:
                    anchors.append((p["start"], p["end"], float(s["height_m"]), "support"))
            anchors.sort()
            for (_, b1, _, _), (a2, _, _, _) in pairwise(anchors):
                if a2 < b1:
                    raise SystemExit(f"{name}: placements overlap at {a2}..{b1}")
            target = np.full(nf, np.nan)
            for a, b, h, _ in anchors:
                target[a:b] = h - obj_low[a:b]
            dz = shifts(target)
            planned = dz.copy()

            # clamps: floor, then supports
            dz = np.maximum(dz, -obj_low)
            xy = np.c_[(pos - o_m) @ u_m, (pos - o_m) @ v_m]
            sup_clamped = np.zeros(nf, bool)
            for s in sup:
                poly = np.asarray(s["patch_xy_m"], np.float64)
                if len(poly) < 3:
                    continue
                h = s["height_m"]
                now = obj_low + dz
                pen = inside(poly, xy, PATCH_MARGIN_M) & (now < h) & (now > h - SUP_PEN_BAND_M)
                dz[pen] = h - obj_low[pen]
                sup_clamped |= pen
            floor_clamped = dz > planned + 1e-9
            floor_clamped &= ~sup_clamped

            held = None
            pz = phys / "out" / f"{name}.npz"
            if pz.exists():
                held = np.load(pz)["held"].astype(bool)
            if move_human and held is None:
                raise SystemExit(f"{name}: --move-human needs {pz}")
            if move_human:
                from scipy.ndimage import gaussian_filter1d
                hdz = gaussian_filter1d(held_weight(held) * dz, HUMAN_SIGMA, mode="nearest")
            else:
                hdz = np.zeros(nf)

            new = pose.copy()
            new[:, :3] = pos + dz[:, None] * n_up
            col = pa.FixedSizeListArray.from_arrays(pa.array(new.astype(np.float32).ravel(), pa.float32()), 7)
            i = table.schema.get_field_index("observation.object.pose")
            out_t = table.set_column(i, table.schema.field(i), col)
            if move_human:
                tr = np.stack(table.column("observation.human.translation").to_numpy(zero_copy_only=False)).astype(np.float64)
                tr = tr + hdz[:, None] * (n_up @ CV_TO_SOMA)  # the translation column is in SOMA's frame (t3_world_probe.F)
                j = out_t.schema.get_field_index("observation.human.translation")
                out_t = out_t.set_column(j, out_t.schema.field(j),
                                         pa.FixedSizeListArray.from_arrays(pa.array(tr.astype(np.float32).ravel(), pa.float32()), 3))
            md = dict(out_t.schema.metadata or {})
            md[b"height_post"] = json.dumps({"from": version, "anchors": len(anchors), "dz_min_m": round(float(dz.min()), 4),
                                             "dz_max_m": round(float(dz.max()), 4), "move_human": move_human,
                                             "human_dz_min_m": round(float(hdz.min()), 4),
                                             "human_dz_max_m": round(float(hdz.max()), 4)}).encode()
            out_t = out_t.replace_schema_metadata(md)
            dst = runs / dst_v / "data" / "chunk-000" / f.name
            dst.parent.mkdir(parents=True, exist_ok=True)
            pq.write_table(out_t, dst)
            (runs / dst_v / "meta").mkdir(exist_ok=True)
            mf = runs / src_v / "meta" / f"episode_{ep:06d}.metadata.json"
            (runs / dst_v / "meta" / mf.name).write_bytes(mf.read_bytes())

            r4 = lambda x: round(float(x), 4)
            row = {"episode": name, "tier": dst_v, "frames": nf,
                   "anchors": [{"start": a, "end": b, "kind": k, "surface_m": r4(h), "dz_m_median": r4(np.median(dz[a:b]))} for a, b, h, k in anchors],
                   "dz_m_min_p50_max": [r4(dz.min()), r4(np.median(dz)), r4(dz.max())],
                   "floor_clamped_frames": int(floor_clamped.sum()), "support_clamped_frames": int(sup_clamped.sum()),
                   "below_floor_before": int((obj_low < -FLOOR_TOL_M).sum()), "below_floor_after": int((obj_low + dz < -1e-6).sum()),
                   "step_max_m_before": r4(np.abs(np.diff(obj_low)).max()), "step_max_m_after": r4(np.abs(np.diff(obj_low + dz)).max())}
            if held is not None and held.any():
                row["held_frames"] = int(held.sum())
                row["held_abs_dz_m_p50_p95_max"] = [r4(np.median(np.abs(dz[held]))), r4(np.percentile(np.abs(dz[held]), 95)), r4(np.abs(dz[held]).max())]
                rel = np.abs(dz - hdz)[held]
                row["held_abs_rel_dz_m_p50_p95_max"] = [r4(np.median(rel)), r4(np.percentile(rel, 95)), r4(rel.max())]
            if move_human:
                row["human_abs_dz_m_p50_p95_max"] = [r4(np.median(np.abs(hdz))), r4(np.percentile(np.abs(hdz), 95)), r4(np.abs(hdz).max())]
                row["human_step_max_m"] = r4(np.abs(np.diff(hdz)).max())
            report.append(row)
            print(json.dumps({k: v for k, v in row.items() if k != "anchors"} | {"anchors": len(anchors)}), flush=True)
    (runs / f"{out_v}.height_post.json").write_text(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
