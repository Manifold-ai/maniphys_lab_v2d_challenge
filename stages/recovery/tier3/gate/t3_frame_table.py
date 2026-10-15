"""Per-frame evidence table of a Tier 3 reference, to set against the policy's per-frame terminations (10-15).

One row per reference frame (the version's frame index = the retargeted reference's), so a failure at frame t can be
looked up against what was known about the reference there:

  state             held / supported / airborne, as t3_dynamics_check judges them on the robot layer (what training sees);
                    label_left / label_right: the reference's own hand_contact_active; limb_d_m: nearest robot hand
                    link surface to the object surface.
  viol_<check>      each t3_dynamics_check violation on that frame (object_any: any object one).
  turn_prev_deg     the version's object turn from the previous frame; dev_local_deg: its distance from the medoid
                    orientation of the frames within LOCAL_HALF either side. Both modulo the object's true symmetries
                    (t3_symmetry). orient_outlier: dev_local_deg > OUTLIER_DEG, i.e. this frame disagrees with most of
                    its neighbours, so one side is wrong, not necessarily this one (ep03 frame 451 is flagged and is
                    the one that matches the video; its neighbours flipped). A run that is wrong throughout (ep03's
                    first rest drawn without its handle) agrees with itself and is not flagged.
  mask_px           object pixels of the SAM2 mask in the main camera (0: not seen: occluded, out of view or lost).
  iou               silhouette IoU of the version's pose against that mask (t3_align_check perframe, every 5th frame;
                    empty elsewhere).
  evidence          ok, or why the frame is weak: no_mask (mask_px < MIN_PX), off_image (iou < IOU_LOW), outlier
                    (orient_outlier), joined by "+".

    T3_GATE=<gate dir> python t3_frame_table.py <tier3 root> <version> <motion set dir> <episodes_metadata.jsonl>
        <support dir> <selection json> <align perframe json> <out dir> [episode,...]
Writes <out dir>/epNN.csv and <out dir>/summary.json.
"""

import csv
import json
import sys
from pathlib import Path

import h5py
import numpy as np
import pyarrow.parquet as pq
import trimesh
from scipy.spatial.transform import Rotation

sys.path.insert(0, str(Path(__file__).resolve().parent))  # run with -I
from t3_dynamics_check import FOOT_TASK, check, supports_of  # noqa: E402
from t3_symmetry import Shape, nearest_equivalent, symmetries  # noqa: E402

LOCAL_HALF = 15  # frames
OUTLIER_DEG = 45.0
MIN_PX = 200
IOU_LOW = 0.5
WORK = {"convert": "work", "convert_v2": "work_v2", "convert_fp": "work_fp", "convert_pivot": "work_fp"}


def ang(a, b):
    return float(np.degrees(np.arccos(np.clip((np.trace(a.T @ b) - 1) / 2, -1, 1))))


def main() -> None:
    root, version, mset, meta = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3]), Path(sys.argv[4])
    sup_dir, sel, align, out = Path(sys.argv[5]), Path(sys.argv[6]), Path(sys.argv[7]), Path(sys.argv[8])
    only = {int(x) for x in sys.argv[9].split(",")} if len(sys.argv) > 9 else None
    out.mkdir(parents=True, exist_ok=True)
    convert = {r["episode"]: r["convert"] for r in json.loads(sel.read_text())}
    iou_of = {}
    for r in json.loads(align.read_text()):
        if version in r and "per_frame" in r[version]:
            iou_of[r["episode"]] = dict(zip(r[version]["per_frame"]["frame"], r[version]["per_frame"]["iou"]))
    metas = {m["episode_index"]: m for m in map(json.loads, (root / "input/meta/episodes_metadata.jsonl").read_text().splitlines()) if m}
    summary = []
    for m in map(json.loads, open(meta)):
        ep, seq = m["episode_index"], m["sequence_id"]
        if only and ep not in only:
            continue
        part = mset / "whole_body/soma" / f"sequence_id={seq}" / "robot_name=g1"
        if not (part / "data.parquet").exists():
            continue
        name = f"ep{ep:02d}_{metas[ep]['object']}"
        res = check(part, supports_of(sup_dir / f"{seq}_support.usda"), feet=bool(FOOT_TASK.search(m["task"])), frames=True)
        pf = res["per_frame"]
        label = np.asarray(pq.read_table(part / "data.parquet", columns=["hand_contact_active", "hand_sides"]).to_pylist()[0]["hand_contact_active"]) > 0.5
        sides = list(pq.read_table(part / "data.parquet", columns=["hand_sides"]).to_pylist()[0]["hand_sides"])
        # the version's orientation (the human-layer data the reference was retargeted from)
        f = None
        for sub in ("", "_suspect"):
            c = root / "runs" / (version + sub) / "data/chunk-000" / f"episode_{ep:06d}.parquet"
            if c.exists():
                f = c
        pose = np.stack(pq.read_table(f, columns=["observation.object.pose"]).column(0).to_numpy(zero_copy_only=False)).astype(np.float64)
        R = Rotation.from_quat(np.c_[pose[:, 4:7], pose[:, 3:4]]).as_matrix()
        n = len(R)
        if n != len(pf["held"]):
            raise SystemExit(f"{name}: {n} version frames, {len(pf['held'])} reference frames")
        mesh = trimesh.load(root / "input" / metas[ep]["mesh"], force="mesh")
        body = mesh if mesh.is_watertight else mesh.convex_hull
        G, axis = symmetries(Shape(mesh, body.center_mass), body.moment_inertia)
        Rc = R.copy()
        if len(G) > 1 or axis is not None:
            for t in range(1, n):
                Rc[t] = nearest_equivalent(R[t], Rc[t - 1], G, axis)
        turn = np.r_[0.0, [ang(Rc[t - 1], Rc[t]) for t in range(1, n)]]
        q = Rotation.from_matrix(Rc).as_quat()
        dev = np.zeros(n)
        for t in range(n):
            a, b = max(0, t - LOCAL_HALF), min(n, t + LOCAL_HALF + 1)
            d = np.abs(q[a:b] @ q[a:b].T).clip(0, 1)
            med = a + int(np.argmax(d.sum(1)))
            dev[t] = ang(Rc[med], Rc[t])
        # image evidence
        H = h5py.File(root / "runs" / WORK[convert[name]] / name / "masks_k0.h5", "r")[f"episode_{ep:06d}"]
        px = np.array([int((H[k][()] > 0).sum()) if (k := f"{t:06d}-k0.obj_rend_mask.png") in H else 0 for t in range(n)])
        iou = iou_of.get(name, {})
        viol = [k for k in pf if k not in ("held", "label", "limb_d", "supported", "gap")]
        rows = []
        for t in range(n):
            state = "held" if pf["held"][t] else ("supported" if pf["supported"][t] else "airborne")
            io = iou.get(t)
            ev = []
            if px[t] < MIN_PX:
                ev.append("no_mask")
            if io is not None and io < IOU_LOW:
                ev.append("off_image")
            if dev[t] > OUTLIER_DEG:
                ev.append("outlier")
            row = {"episode": ep, "frame": t, "state": state,
                   "label_left": int(label[sides.index("left"), t]), "label_right": int(label[sides.index("right"), t]),
                   "limb_d_m": round(float(pf["limb_d"][t]), 4),
                   **{f"viol_{k}": int(bool(pf[k][t])) for k in viol},
                   "turn_prev_deg": round(float(turn[t]), 1), "dev_local_deg": round(float(dev[t]), 1),
                   "orient_outlier": int(dev[t] > OUTLIER_DEG), "mask_px": int(px[t]),
                   "iou": "" if io is None else round(float(io), 3), "evidence": "+".join(ev) or "ok"}
            rows.append(row)
        with open(out / f"ep{ep:02d}.csv", "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        ev = np.array([r["evidence"] for r in rows])
        s = {"episode": name, "frames": n, "held": int(pf["held"].sum()), "object_viol": int(pf["object_any"].sum()),
             "orient_outlier": int((dev > OUTLIER_DEG).sum()), "no_mask": int((px < MIN_PX).sum()),
             "off_image_sampled": int(sum(1 for v in iou.values() if v < IOU_LOW)), "sampled": len(iou),
             "weak_evidence": int((ev != "ok").sum())}
        summary.append(s)
        print(json.dumps(s), flush=True)
    (out / "summary.json").write_text(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
