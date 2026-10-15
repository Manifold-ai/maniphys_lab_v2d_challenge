"""Why kf2 has more rot_drift (ep01/03/27) and lin_airborne (ep06) than dyn7 (diagnosis only).
For each set: per unheld run, the frames flagged rot_drift, the largest single-frame turn inside the run (a reset jumps,
a creep does not), and the turn from the run start at its end; for ep06 the support gap on frames kf2 calls airborne.
"""
import json
import os
import sys
from pathlib import Path

import numpy as np

G = "/lab_data/yqchen/v2d/gate"
sys.path.insert(0, G)
os.environ.setdefault("T3_GATE", G)
import t3_dynamics_check as dc  # noqa: E402

META = f"{G}/repo/runs/tier3/root_bdyn7/meta/episodes_metadata.jsonl"
metas = {m["episode_index"]: m for m in map(json.loads, open(META)) if m}


def per_frame(s, ep):
    m = metas[ep]
    part = Path(f"{G}/repo/runs/motion/tier3_{s}/whole_body/soma/sequence_id={m['sequence_id']}/robot_name=g1")
    sup = dc.supports_of(Path(f"{G}/support_usda_bhm/{m['sequence_id']}_support.usda"))
    e = dc.check(part, sup, feet=bool(dc.FOOT_TASK.search(m["task"])), frames=True)
    import pyarrow.parquet as pq
    r = pq.read_table(part / "data.parquet", columns=["object_body_wxyz", "object_body_position"]).to_pylist()[0]
    R = dc.quat_R(np.array([b[0] for b in r["object_body_wxyz"]]))
    return e["per_frame"], R


def step(R):
    d = np.einsum("tij,tkj->tik", R[1:], R[:-1])
    return np.r_[0, np.degrees(np.arccos(np.clip((np.trace(d, axis1=1, axis2=2) - 1) / 2, -1, 1)))]


for ep in (1, 3, 27):
    for s in ("bdyn7", "bkf2"):
        pf, R = per_frame(s, ep)
        st = step(R)
        out = []
        for a, b in dc.runs(~pf["held"]):
            k = int(pf["rot_drift"][a:b].sum())
            if k == 0:
                continue
            i = a + int(np.argmax(st[a:b]))
            out.append(f"[{a},{b}) drift {k} maxstep {st[i]:.1f}@{i} start->end {np.degrees(np.arccos(np.clip((np.trace(R[a].T @ R[b-1]) - 1) / 2, -1, 1))):.1f}")
        print(f"ep{ep:02d} {s}: " + " | ".join(out), flush=True)
for s in ("bdyn7", "bkf2"):
    pf, R = per_frame(s, 6)
    air = np.flatnonzero(~pf["held"] & ~pf["supported"])
    print(f"ep06 {s}: airborne {len(air)} frames {air[:3].tolist()}..{air[-3:].tolist() if len(air) else []}; gap mm on unheld p50/max "
          f"{np.percentile(pf['gap'][~pf['held']] * 1000, 50):.1f}/{pf['gap'][~pf['held']].max() * 1000:.1f}; airborne gap mm p50 "
          f"{(np.median(pf['gap'][air]) * 1000 if len(air) else 0):.1f}", flush=True)
