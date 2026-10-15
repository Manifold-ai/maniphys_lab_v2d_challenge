"""Locate rot_jump / rot_torque frames per set and classify them (diagnosis only, report-only).

For every rot_jump frame t in each set: jump angle, held/supported state, whether the same frame jumps in the
input (best_hm), whether the jump returns (a short flip: some frame within RET frames lands back within SYM_M of
the pre-jump pose), and whether t lies in a dyn7 locked run, at a locked-run boundary, or inside a held run.
usage: rotjump_locate.py <out.json>
"""
import json
import os
import sys
from multiprocessing import Pool

import numpy as np

G = "/lab_data/yqchen/v2d/gate"
sys.path.insert(0, G)
os.environ.setdefault("T3_GATE", G)
import t3_dynamics_check as dc  # noqa: E402
from t3_symmetry import SYM_M  # noqa: E402

SETS = ["bhm", "bdyn4", "bdyn7"]
RET = 15
META = f"{G}/repo/runs/tier3/root_bdyn7/meta/episodes_metadata.jsonl"
POST = "/lab_data/yqchen/v2d/tier3/runs/tier3_cari4d_f830_best_dyn7.dynamics_post.json"


def one(args):
    s, m = args
    from pathlib import Path
    import pyarrow.parquet as pq
    import trimesh
    seq = m["sequence_id"]
    part = Path(f"{G}/repo/runs/motion/tier3_{s}/whole_body/soma/sequence_id={seq}/robot_name=g1")
    if not (part / "data.parquet").exists():
        return s, m["episode_index"], None
    sup = dc.supports_of(Path(f"{G}/support_usda_bhm/{seq}_support.usda"))
    e = dc.check(part, sup, feet=bool(dc.FOOT_TASK.search(m["task"])), frames=True)
    pf = e["per_frame"]
    r = pq.read_table(part / "data.parquet", columns=["object_body_wxyz"]).to_pylist()[0]
    R = dc.quat_R(np.array([b[0] for b in r["object_body_wxyz"]]))
    mesh = trimesh.load(part.parent / "object" / "textured_mesh.obj", force="mesh", process=False)
    body = mesh if mesh.is_watertight else mesh.convex_hull
    shape = dc.Shape(mesh, np.asarray(body.center_mass))
    n = len(R)
    dq = np.einsum("tij,tkj->tik", R[1:], R[:-1])
    ang = np.degrees(np.arccos(np.clip((np.trace(dq, axis1=1, axis2=2) - 1) / 2, -1, 1)))
    rows = []
    for t in np.flatnonzero(pf["rot_jump"]):
        back = None
        for k in range(t, min(n, t + RET)):
            if shape.shift(R[t - 1].T @ R[k]) < SYM_M:
                back = int(k - t)
                break
        rows.append({"t": int(t), "deg": round(float(ang[t - 1]), 1), "held": bool(pf["held"][t]),
                     "supported": bool(pf["supported"][t]), "returns_after": back})
    tor = np.flatnonzero(pf["rot_torque"])
    return s, m["episode_index"], {"jumps": rows, "torque_frames": tor.tolist(), "n": n,
                                   "held": np.flatnonzero(pf["held"]).tolist()}


def main():
    metas = [json.loads(x) for x in open(META) if x.strip()]
    with Pool(4) as p:
        res = p.map(one, [(s, m) for s in SETS for m in metas])
    out = {s: {} for s in SETS}
    for s, ep, r in res:
        if r is not None:
            out[s][f"ep{ep:02d}"] = r
    post = {row["episode"][:4]: row for row in json.load(open(POST))}
    out["dyn7_locked"] = {k: [[x["start"], x["end"]] for x in v["locked_runs"]] for k, v in post.items()}
    out["dyn7_dropped"] = {k: v["rot_offsets_dropped"] for k, v in post.items()}
    json.dump(out, open(sys.argv[1], "w"))
    print("DONE")


if __name__ == "__main__":
    main()
