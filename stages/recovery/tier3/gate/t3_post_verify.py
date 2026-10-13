"""Independent check of a t3_depth_post.py version, from the written parquet only (not the post-process's own numbers).

Recomputes each frame's lowest hull point from the written object pose: every rest anchor's median lowest point must be
on its surface, no frame below the floor. Also counts frames with a vertical part and with the depth cap reached, from
the post-process's dump. Run from the tier3 root:
    python t3_post_verify.py <version> <dump dir> [max anchor offset mm, default 5]
Exits 1 when an anchor is off by more than the limit or a frame is below the floor.
"""
import json, sys, numpy as np, pyarrow.parquet as pq, trimesh
sys.path.insert(0, "code/stages/recovery/tier3")
import t3_inputs
from t3_support import basis
from scipy.spatial.transform import Rotation
ver, dump = sys.argv[1], sys.argv[2]
limit_mm = float(sys.argv[3]) if len(sys.argv) > 3 else 5.0
metas = {m["episode_index"]: m for m in map(json.loads, open("input/meta/episodes_metadata.jsonl").read().splitlines()) if m}
worst = 0.0; below = 0; vfr = 0; tot = 0; capped = 0
for r in json.load(open(f"runs/{ver}.depth_post.json")):
    ep = int(r["episode"][2:4]); m = metas[ep]; sub = "_suspect" if "suspect" in r["tier"] else ""
    p = np.stack(pq.read_table(f"runs/{ver}{sub}/data/chunk-000/episode_{ep:06d}.parquet").column("observation.object.pose").to_numpy(zero_copy_only=False)).astype(float)
    n, d, _, _, _ = basis(t3_inputs.ground_plane(".", m))
    hull = np.asarray(trimesh.load("input/" + m["mesh"], force="mesh").convex_hull.vertices)
    R = Rotation.from_quat(np.c_[p[:, 4:7], p[:, 3:4]]).as_matrix()
    low = ((np.einsum("fij,kj->fki", R, hull) + p[:, None, :3]) @ n + d).min(1)
    below += int((low < -1e-4).sum())
    for a in r["anchors"]:
        worst = max(worst, abs(np.median(low[a["start"]:a["end"]]) - a["surface_m"]))
    z = np.load(f"{dump}/{r['episode']}.npz")
    vfr += int((np.abs(z["vert"]) > 1e-4).sum()); tot += len(z["vert"]); capped += r["k_capped_frames"]
print("独立重算：锚定段最低点中位与支撑面之差最大 %.1f mm；低于地面 0.1 mm 以上的帧 %d" % (worst * 1000, below))
print("用到竖直补偿的帧 %d / %d（%.1f%%）；深度比例触到上限的帧 %d" % (vfr, tot, 100 * vfr / tot, capped))
if worst * 1000 > limit_mm or below:
    raise SystemExit(f"FAIL: anchor offset {worst * 1000:.1f} mm (limit {limit_mm}), {below} frames below the floor")
print("VERIFY_OK")
