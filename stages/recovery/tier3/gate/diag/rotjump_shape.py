"""Shape of each dyn7 rot_jump (diagnosis only): angle, body-frame axis vs principal axes, the smallest rotation back to
the pre-jump pose within RET frames, and the cluster it belongs to (jumps <= GAP frames apart).
usage: rotjump_shape.py <rotjump.json> <set> <out.json>
"""
import json
import sys
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import trimesh

G = "/lab_data/yqchen/v2d/gate"
sys.path.insert(0, G)
import t3_dynamics_check as dc  # noqa: E402

RET, GAP = 30, 10
META = f"{G}/repo/runs/tier3/root_bdyn7/meta/episodes_metadata.jsonl"


def ang(a, b):
    return float(np.degrees(np.arccos(np.clip((np.trace(a.T @ b) - 1) / 2, -1, 1))))


def main():
    d = json.load(open(sys.argv[1]))
    s = sys.argv[2]
    metas = {f"ep{m['episode_index']:02d}": m for m in map(json.loads, open(META)) if m}
    out = {}
    for ep, r in d[s].items():
        if not r["jumps"]:
            continue
        seq = metas[ep]["sequence_id"]
        part = Path(f"{G}/repo/runs/motion/tier3_{s}/whole_body/soma/sequence_id={seq}/robot_name=g1")
        q = np.array([b[0] for b in pq.read_table(part / "data.parquet", columns=["object_body_wxyz"]).to_pylist()[0]["object_body_wxyz"]])
        R = dc.quat_R(q)
        mesh = trimesh.load(part.parent / "object" / "textured_mesh.obj", force="mesh", process=False)
        body = mesh if mesh.is_watertight else mesh.convex_hull
        P = np.asarray(body.principal_inertia_vectors)  # rows
        n = len(R)
        rows = []
        for j in r["jumps"]:
            t = j["t"]
            dR = R[t - 1].T @ R[t]  # body frame
            w = np.array([dR[2, 1] - dR[1, 2], dR[0, 2] - dR[2, 0], dR[1, 0] - dR[0, 1]])
            if np.linalg.norm(w) < 1e-9:  # ~180 deg: axis from the symmetric part
                vals, vecs = np.linalg.eigh(dR + dR.T)
                w = vecs[:, -1]
            w = w / np.linalg.norm(w)
            align = np.abs(P @ w)
            back = [ang(R[t - 1], R[k]) for k in range(t, min(n, t + RET))]
            rows.append({"t": t, "deg": round(ang(R[t - 1], R[t]), 1), "held": j["held"],
                         "axis_principal": int(np.argmax(align)), "axis_align": round(float(align.max()), 3),
                         "min_back_deg": round(min(back), 1), "min_back_at": int(np.argmin(back))})
        cl, cur = [], []
        for x in rows:
            if cur and x["t"] - cur[-1]["t"] > GAP:
                cl.append(cur)
                cur = []
            cur.append(x)
        if cur:
            cl.append(cur)
        out[ep] = {"rows": rows, "clusters": [[c[0]["t"], c[-1]["t"], len(c)] for c in cl]}
    json.dump(out, open(sys.argv[3], "w"))
    print("DONE")


if __name__ == "__main__":
    main()
