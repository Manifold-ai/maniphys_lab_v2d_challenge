"""Diagnose where rest_drift / rot_drift / lin_airborne come from (10-16, ep28/29/13): per unheld run of the check, its
contact states, how far the object moves, how near a hand is, and what the post-process (human-layer held + height_post
anchors) thought of the same frames.   python diag/unheld_runs.py <set> <ep> ...   (set e.g. bdyn7; human layer = best_hm)"""
import json, os, sys
from pathlib import Path
import numpy as np
import pyarrow.parquet as pq
G = "/lab_data/yqchen/v2d/gate"; T = "/lab_data/yqchen/v2d/tier3"
sys.path.insert(0, G); os.environ.setdefault("T3_GATE", G)
import t3_dynamics_check as dc
s = sys.argv[1]
metas = {m["episode_index"]: m for m in map(json.loads, open(f"{G}/repo/runs/tier3/root_{s}/meta/episodes_metadata.jsonl")) if m}
tm = {m["episode_index"]: m for m in map(json.loads, open(f"{T}/input/meta/episodes_metadata.jsonl")) if m}
anch = {r["episode"]: r["anchors"] for r in json.load(open(f"{T}/runs/tier3_cari4d_f830_best_hm.height_post.json"))}
for ep in map(int, sys.argv[2:]):
    m = metas[ep]; name = f"ep{ep:02d}_{tm[ep]['object']}"
    part = Path(f"{G}/repo/runs/motion/tier3_{s}/whole_body/soma/sequence_id={m['sequence_id']}/robot_name=g1")
    sup = dc.supports_of(Path(f"{G}/support_usda_bhm/{m['sequence_id']}_support.usda"))
    e = dc.check(part, sup, feet=bool(dc.FOOT_TASK.search(m["task"])), frames=True)
    pf = e["per_frame"]; n = e["frames"]
    r = pq.read_table(part / "data.parquet", columns=["object_body_position"]).to_pylist()[0]
    pos = np.array([b[0] for b in r["object_body_position"]])
    hh = np.load(f"{T}/runs/physics/tier3_cari4d_f830_best_hm/out/{name}.npz")["held"].astype(bool)
    rest = np.zeros(n, bool)
    for a in anch.get(name, []): rest[a["start"]:a["end"]] = True
    print(f"\n## {name}  task: {m['task']}")
    print(f"frames {n}; check held {pf['held'].mean():.2f} (label {pf['label'].mean():.2f}) supported {pf['supported'].mean():.2f} airborne {(~pf['held'] & ~pf['supported']).mean():.2f}; human-layer held {hh.mean():.2f}, height_post rest {rest.mean():.2f}")
    print(f"violations {e['count']}")
    print("unheld run [s,e) len | supported/airborne share | gap mm p50 | com move m max | hand dist cm min/p50 | human held share, anchored share | viol: drift/rot_drift/air")
    for a, b in dc.runs(~pf["held"]):
        if b - a < 8: continue
        mv = np.linalg.norm(pos[a:b, :2] - pos[a, :2], axis=1).max()
        ld = pf["limb_d"][a:b] * 100
        print(f"[{a},{b}) {b-a:4d} | {pf['supported'][a:b].mean():.2f}/{1-pf['supported'][a:b].mean():.2f} | {np.median(pf['gap'][a:b])*1000:6.0f} | {mv:.3f} | {np.nanmin(ld):5.1f}/{np.nanmedian(ld):5.1f} | {hh[a:b].mean():.2f}, {rest[a:b].mean():.2f} | {pf['rest_drift'][a:b].sum()}/{pf['rot_drift'][a:b].sum()}/{pf['lin_airborne'][a:b].sum()}")
