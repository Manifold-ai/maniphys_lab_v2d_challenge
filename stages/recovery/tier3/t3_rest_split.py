"""On rest frames, how much of the lowest point's wander comes from the object's orientation and how much from its position.

The lowest hull point's height splits exactly: low = n.p + d + min_i n.(R v_i), the centre's height (position term) plus
how far the hull reaches below the centre in the current orientation (orientation term). On an unheld rest the true
object neither moves nor turns, so both terms should be constant and low should equal the surface height. Per rest
segment (t3_depth_post.py's anchors: floor static segments, t3_support's on_floor runs, support placements; unheld frames
only): the mean offset from the surface (a constant per segment), the per-frame spread of low, of each term, and their
correlation (negative: the fit trades orientation against position). If the spread is mostly orientation, snapping each
frame's lowest point to the surface by moving the object corrects an orientation error with a translation (10-13: the
weighted ray/normal correction moved objects off their silhouettes on ep02/04/09/25/27 while the image said they sat right).

    python t3_rest_split.py <tier3 root> <version> <support dir> <physics dir> <out json>
"""

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import t3_inputs  # noqa: E402
from t3_support import FLOOR_TOL_M, basis, static_segments  # noqa: E402

MIN_FRAMES = 10


def main() -> None:
    import pyarrow.parquet as pq
    import trimesh
    from scipy.spatial.transform import Rotation

    root, version, sup_dir, phys, out = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3]), Path(sys.argv[4]), Path(sys.argv[5])
    metas = {m["episode_index"]: m for m in map(json.loads, (root / "input/meta/episodes_metadata.jsonl").read_text().splitlines()) if m}
    rows = []
    for sub in ("", "_suspect"):
        for f in sorted((root / "runs" / (version + sub) / "data/chunk-000").glob("episode_*.parquet")):
            p = np.stack(pq.read_table(f).column("observation.object.pose").to_numpy(zero_copy_only=False)).astype(float)
            ep = int(f.stem.split("_")[1])
            m = metas[ep]
            name = f"ep{ep:02d}_{m['object']}"
            n, d, _, _, _ = basis(t3_inputs.ground_plane(root, m))
            hull = np.asarray(trimesh.load(root / "input" / m["mesh"], force="mesh").convex_hull.vertices, np.float64)
            rot = Rotation.from_quat(np.c_[p[:, 4:7], p[:, 3:4]]).as_matrix()
            pos = p[:, :3]
            t_pos = pos @ n + d                                          # centre height
            t_rot = np.einsum("fij,kj->fki", rot, hull) @ n               # hull points below the centre, per orientation
            t_rot = t_rot.min(1)
            low = t_pos + t_rot
            held = np.load(phys / "out" / f"{name}.npz")["held"].astype(bool)
            sj = json.loads((sup_dir / f"{name}.json").read_text()) if (sup_dir / f"{name}.json").exists() else {}
            segs = [(a, b, 0.0, "floor") for a, b in static_segments(pos) if np.median(low[a:b]) <= FLOOR_TOL_M]
            segs += [(a, b, 0.0, "floor") for r in sj.get("rejected", []) if r["status"] == "on_floor" for a, b in r["floor_runs"]]
            segs += [(q["start"], q["end"], float(s["height_m"]), "support") for s in sj.get("supports", []) for q in s["placements"]]
            out_segs = []
            for a, b, h, kind in sorted(segs):
                fr = np.arange(a, b)[~held[a:b]]
                if len(fr) < MIN_FRAMES:
                    continue
                lp, lr, lo = t_pos[fr], t_rot[fr], low[fr]
                c = float(np.corrcoef(lp, lr)[0, 1]) if lp.std() > 1e-6 and lr.std() > 1e-6 else None
                out_segs.append({"start": int(a), "end": int(b), "kind": kind, "frames": int(len(fr)),
                                 "mean_offset_cm": round(float((lo - h).mean()) * 100, 2),
                                 "low_std_cm": round(float(lo.std()) * 100, 2),
                                 "position_std_cm": round(float(lp.std()) * 100, 2),
                                 "orientation_std_cm": round(float(lr.std()) * 100, 2),
                                 "corr": round(c, 3) if c is not None else None})
            if not out_segs:
                continue
            w = np.array([s["frames"] for s in out_segs], float)
            agg = lambda k: round(float(np.sqrt((w * np.array([s[k] for s in out_segs]) ** 2).sum() / w.sum())), 2)
            row = {"episode": name, "segments": out_segs, "rest_frames": int(w.sum()),
                   "mean_offset_cm_abs_wmean": round(float((w * np.abs([s["mean_offset_cm"] for s in out_segs])).sum() / w.sum()), 2),
                   "low_std_cm_rms": agg("low_std_cm"), "position_std_cm_rms": agg("position_std_cm"),
                   "orientation_std_cm_rms": agg("orientation_std_cm")}
            rows.append(row)
            print(json.dumps({k: v for k, v in row.items() if k != "segments"}), flush=True)
    out.write_text(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()
