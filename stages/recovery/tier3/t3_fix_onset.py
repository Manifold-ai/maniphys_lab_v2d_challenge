"""Object motion before contact on a delivered Tier 3 version, t3fix part C, classification step (Tier 3 inputs only).

Plan: agent-doc/plan-t3fix-2026-10-27.md on track2/p1-training, version 2, section 1 C1-C2.

Per episode, every run of unheld frames (the physics check's held flags, closed over GAP frames as
t3_dynamics_post.py does; a contact joint within HOLD_M = 0.10 m) of at least MIN_RUN frames is classified by comparing
the reference with the video:
  - ref_move_m: the largest move of the object's centre of mass from the run's first frame, on the delivered layer;
  - on the frames with mask evidence (object mask pixels outside the person >= MIN_MASK_PX), the SAM2 object mask
    against the run's first evidence frame: centroid shift (px), IoU, area ratio.
Classes:
  locked       dyn7 already locked every frame of the run (nothing to do);
  drift        ref_move_m > REF_M while the mask stays put (centroid <= MASK_PX, IoU >= MASK_IOU, area ratio within
               AREA_TOL), and one frozen pose (centre of mass at the median, orientation at dyn7's robust mean) fits the
               video no worse than the reference on every evidence frame (IoU >= the reference's - FREEZE_TOL);
  hand_late    the mask moves (centroid > MASK_PX or area ratio outside AREA_TOL) while no hand is near;
  still        ref_move_m <= REF_M and the mask stays put;
  inconclusive everything else (too little evidence, IoU below MASK_IOU with centroid and area inside, guard failed).
Only drift runs become anchors for the apply step; the object of a hand_late run is the scored trajectory and is
left alone. Nothing is written into the version.

    python t3_fix_onset.py <tier3 root> <selection json> <version> <physics dir> <out dir> [only=<ep>,..]
Writes <out>/epNN.json; one json line per episode on stdout. CPU only.
"""

import json
import os
import sys
import time
from pathlib import Path

import numpy as np
from scipy.ndimage import binary_closing

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE / "gate"), str(HERE.parents[2] / "libs" / "v2d_infra")]

GAP = 5  # frames, as t3_dynamics_post.GAP
MIN_RUN = 15  # frames
MIN_EVIDENCE = 10
REF_M = 0.03
MASK_PX = 15.0
MASK_IOU = 0.8
AREA_TOL = 0.05
FREEZE_TOL = 0.02


def mask_stats(obj_masks: list[np.ndarray]) -> dict:
    """Centroid shift (px), IoU and area ratio of each mask against the first."""
    base = obj_masks[0]
    ys, xs = np.nonzero(base)
    c0, a0 = np.array([xs.mean(), ys.mean()]), float(base.sum())
    shift, iou, area = [], [], []
    for mk in obj_masks:
        ys, xs = np.nonzero(mk)
        shift.append(float(np.linalg.norm(np.array([xs.mean(), ys.mean()]) - c0)))
        iou.append(float((mk & base).sum()) / max(1.0, float((mk | base).sum())))
        area.append(float(mk.sum()) / a0)
    return {"shift_px_max": max(shift), "iou_min": min(iou), "area_min": min(area), "area_max": max(area)}


def classify(ref_move_m: float, stats: dict | None, evidence: int, guard_ok: bool | None) -> str:
    if stats is None or evidence < MIN_EVIDENCE:
        return "inconclusive"
    area_in = 1 - AREA_TOL <= stats["area_min"] and stats["area_max"] <= 1 + AREA_TOL
    put = stats["shift_px_max"] <= MASK_PX and stats["iou_min"] >= MASK_IOU and area_in
    moves = stats["shift_px_max"] > MASK_PX or not area_in
    if put and ref_move_m <= REF_M:
        return "still"
    if put and ref_move_m > REF_M:
        return "drift" if guard_ok else "inconclusive"
    if moves:
        return "hand_late"
    return "inconclusive"


def main() -> None:
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    import h5py
    import trimesh
    from tier_guard import forbid_lower_tiers
    forbid_lower_tiers()  # Tier 3: nothing from Tier 1 or Tier 2 (Kaggle 2.8.c)
    from t3_align_check import WORK, similarity, world_pose
    from t3_dynamics_post import robust_mean
    from t3_fix_units import runs
    from t3_frame_confidence import silhouette
    from t3_object_check import load_mesh
    from t3_track_check import MIN_MASK_PX

    args = [a for a in sys.argv[1:] if "=" not in a]
    kv = dict(a.split("=", 1) for a in sys.argv[1:] if "=" in a)
    root, sel, version, phys, out = Path(args[0]), Path(args[1]), args[2], Path(args[3]), Path(args[4])
    only = {int(x) for x in kv.get("only", "").split(",") if x}
    out.mkdir(parents=True, exist_ok=True)
    metas = {m["episode_index"]: m for m in map(json.loads, (root / "input/meta/episodes_metadata.jsonl").read_text().splitlines()) if m}
    dyn = json.loads((root / "runs" / f"{version}.dynamics_post.json").read_text())
    locked_runs = {r["episode"]: r["locked_runs"] for r in dyn}
    for r in json.loads(sel.read_text()):
        ep, name, conv = r["episode_index"], r["episode"], r["convert"]
        if only and ep not in only:
            continue
        t0 = time.time()
        m = metas[ep]
        s, rot_, t, k, _ = similarity(root / "runs" / conv / name)
        verts, faces = load_mesh(root / "input" / m["mesh"])
        mesh = trimesh.load(root / "input" / m["mesh"], force="mesh")
        body = mesh if mesh.is_watertight else mesh.convex_hull
        com_b = np.asarray(body.center_mass, np.float64)
        Tw = world_pose(root, version, ep)
        n = len(Tw)
        com = np.einsum("nij,j->ni", Tw[:, :3, :3], com_b) + Tw[:, :3, 3]
        held = np.load(phys / "out" / f"{name}.npz")["held"].astype(bool)
        if len(held) != n:
            raise SystemExit(f"{name}: {len(held)} held flags for {n} frames")
        held = binary_closing(held, np.ones(2 * GAP + 1, bool)) | held
        locked = np.zeros(n, bool)
        for lr in locked_runs.get(name, []):
            locked[lr["start"]:lr["end"]] = True
        H = h5py.File(root / "runs" / WORK[conv] / name / "masks_k0.h5", "r")[f"episode_{ep:06d}"]

        def masks(f):
            ok, pk = f"{f:06d}-k0.obj_rend_mask.png", f"{f:06d}-k0.person_mask.png"
            if ok not in H:
                return None, None
            obj = H[ok][()] > 0
            return obj, (H[pk][()] > 0 if pk in H else np.zeros_like(obj))

        rows = []
        for a, b in runs(~held):
            if b - a < MIN_RUN:
                continue
            row = {"start": a, "end": b, "ref_move_m": round(float(np.linalg.norm(com[a:b] - com[a], axis=1).max()), 4)}
            if locked[a:b].all():
                rows.append({**row, "class": "locked"})
                continue
            ev, objs = [], []
            for f in range(a, b):
                obj, person = masks(f)
                if obj is not None and (obj & ~person).sum() >= MIN_MASK_PX:
                    ev.append(f)
                    objs.append(obj)
            stats = mask_stats(objs) if objs else None
            guard_ok = None
            if stats is not None and row["ref_move_m"] > REF_M:
                Tf = np.eye(4)
                Tf[:3, :3] = robust_mean(Tw[a:b, :3, :3])[0]
                Tf[:3, 3] = np.median(com[a:b], axis=0) - Tf[:3, :3] @ com_b
                worse = 0
                for f in ev:
                    obj, person = masks(f)
                    i0 = silhouette(verts, faces, Tw[f], rot_, t, s, k, obj, person)[1]
                    i1 = silhouette(verts, faces, Tf, rot_, t, s, k, obj, person)[1]
                    worse += int(i1 < i0 - FREEZE_TOL)
                guard_ok = worse == 0
                row["freeze_worse_frames"] = worse
            cls = classify(row["ref_move_m"], stats, len(ev), guard_ok)
            rows.append({**row, "evidence": len(ev), **({k_: round(v, 4) for k_, v in stats.items()} if stats else {}),
                         "locked_frames": int(locked[a:b].sum()), "class": cls})
        summary = {"episode": name, "frames": n, "held_share": round(float(held.mean()), 3), "runs": len(rows),
                   **{c: sum(x["class"] == c for x in rows) for c in ("drift", "hand_late", "still", "locked", "inconclusive")},
                   "drift_frames": sum(x["end"] - x["start"] for x in rows if x["class"] == "drift"),
                   "seconds": round(time.time() - t0, 1)}
        (out / f"ep{ep:02d}.json").write_text(json.dumps({**summary, "thresholds": {
            "gap": GAP, "min_run": MIN_RUN, "min_evidence": MIN_EVIDENCE, "ref_m": REF_M, "mask_px": MASK_PX,
            "mask_iou": MASK_IOU, "area_tol": AREA_TOL, "freeze_tol": FREEZE_TOL}, "rows": rows}, indent=1))
        print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
