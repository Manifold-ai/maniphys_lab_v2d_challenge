import json, os, sys
from pathlib import Path
import numpy as np
G = "/lab_data/yqchen/v2d/gate"; sys.path.insert(0, G); os.environ.setdefault("T3_GATE", G)
import t3_dynamics_check as dc
import pyarrow.parquet as pq, trimesh
m = [json.loads(x) for x in open(f"{G}/repo/runs/tier3/root_bdyn7/meta/episodes_metadata.jsonl") if json.loads(x)["episode_index"] == 6][0]
seq = m["sequence_id"]
for sup_dir in ("support_usda_bhm", "support_usda_bdyn7"):
    print(sup_dir, [(lo.round(3).tolist(), hi.round(3).tolist(), round(top, 3)) for lo, hi, top in dc.supports_of(Path(f"{G}/{sup_dir}/{seq}_support.usda"))])
for s in ("bdyn7", "bkf2"):
    part = Path(f"{G}/repo/runs/motion/tier3_{s}/whole_body/soma/sequence_id={seq}/robot_name=g1")
    r = pq.read_table(part / "data.parquet", columns=["object_body_wxyz", "object_body_position"]).to_pylist()[0]
    pos = np.array([b[0] for b in r["object_body_position"]]); R = dc.quat_R(np.array([b[0] for b in r["object_body_wxyz"]]))
    mesh = trimesh.load(part.parent / "object" / "textured_mesh.obj", force="mesh", process=False)
    body = mesh if mesh.is_watertight else mesh.convex_hull
    com = pos + R @ np.asarray(body.center_mass)
    low = np.einsum("tij,vj->tvi", R, np.asarray(mesh.convex_hull.vertices))[..., 2].min(1) + pos[:, 2]
    for t in (440, 455, 500, 545):
        print(s, t, "com xy", com[t, :2].round(3).tolist(), "low z", round(float(low[t]), 3))
