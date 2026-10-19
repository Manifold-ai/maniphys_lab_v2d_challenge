"""Silhouette IoU of several versions on every <stride>-th frame (10-19: the init pilot's position check, then
t3_sel_pilot.sh; the pose path is t3_pose_overlay.py's, the masks t3_object_check.py's, the similarity of convert_fp_gb4).

    python mix_iou.py <root> <ep> <episode name> <stride> <version>...
"""

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from t3_align_check import similarity, world_pose  # noqa: E402
from t3_object_check import MIN_VISIBLE_PX, load_mesh, rasterise, visible_iou  # noqa: E402

root, ep, name, stride, versions = Path(sys.argv[1]), int(sys.argv[2]), sys.argv[3], int(sys.argv[4]), sys.argv[5:]
meta = next(m for m in map(json.loads, (root / "input/meta/episodes_metadata.jsonl").read_text().splitlines()) if m and m["episode_index"] == ep)
V, F = load_mesh(root / "input" / meta["mesh"])
s, rot, t, K, _ = similarity(root / "runs" / "convert_fp_gb4" / name)
poses = {v: world_pose(root, v, ep) for v in versions}
n = {len(p) for p in poses.values()}
assert len(n) == 1, n
masks = root / "runs" / "work_fp" / name / "sam2_masks"
for f in range(0, n.pop(), stride):
    om = masks / "1" / f"{f:06d}.png"
    if not om.exists():
        continue
    obj = np.asarray(Image.open(om).convert("L")) > 0
    pm = masks / "0" / f"{f:06d}.png"
    person = np.asarray(Image.open(pm).convert("L")) > 0 if pm.exists() else np.zeros_like(obj)
    row = {"frame": f, "mask_px": int(obj.sum())}
    for v in versions:
        pw = poses[v][f]
        R_c, p_c = rot.T @ pw[:3, :3], rot.T @ (pw[:3, 3] - t) / s
        rend = rasterise(V @ R_c.T + p_c, F, K, *obj.shape)
        inter, union = (rend & obj).sum(), (rend | obj).sum()
        rv, mv = rend & ~person, obj & ~person
        vis = None if rv.sum() < MIN_VISIBLE_PX or mv.sum() < MIN_VISIBLE_PX else round(visible_iou(rv, mv), 4)
        row[v] = {"all": round(float(inter) / float(union), 4) if union else None, "vis": vis}
    print(json.dumps(row), flush=True)
