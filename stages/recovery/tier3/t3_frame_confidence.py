"""Per-frame confidence of a Tier 3 version's object pose, from Tier 3 inputs only (10-22, self-check item 13).

The delivered parquet carries no per-frame trust: observation.object.visible is all true (t3_convert_ep.py writes ones),
and rxzhou's challenge_to_soma.py holds the last visible pose over frames marked invisible, so a trust signal written
there would change the training reference. This writes it beside the data instead, one row per frame in
<version dir>/confidence/episode_<ep>.parquet; nothing downstream reads it unless asked to.

Per frame, on the delivered layer (the version's world pose and body, mapped back to the exo camera by the world step's
similarity, as t3_align_check.py):
  - silhouette: the official mesh at the delivered pose against the SAM2 object mask, person pixels removed from both;
    IoU of the two dilated by DILATE_PX, and the centroid offset (t3_track_check.py's measure and thresholds). Bad when
    the visible mask has at least MIN_MASK_PX pixels and IoU < SIL_IOU or the centroids are more than SIL_CENTROID_PX
    apart. Under MIN_MASK_PX there is no evidence either way (the person hides the object, or it is out of view).
  - jump: the pose moves more than JUMP_M from the previous frame.
  - unheld motion: the object moves faster than MOVING_MPS (smoothed) while no contact joint is within HAND_M of its
    surface (contact joints as t3_track_check.py: the hands, plus the feet when the task text names a foot).
  - locked: the frame is in a run t3_dynamics_post.py locked to one pose. Reported, not judged.
label: "bad" when any of the three flags is set, else "unverified" without silhouette evidence, else "ok". lost: bad
frames closed over CLOSE_GAP and runs of at least MIN_SEGMENT kept, t3_track_check.py's lost segments. The thresholds
are t3_track_check.py's, not tuned here; the user's checked frames only evaluate them.
What "ok" cannot see: an orientation that keeps the silhouette. On gb5 the cup handle the user judged wrong at
ep03 frames 117 and 563, and ep13's wrong orientation at frames 720 and 921, are all ok; a lost track (ep13 189/769,
ep28) and an occluded object (ep02 from frame 900) are what it marks.

    python t3_frame_confidence.py <tier3 root> <selection json> <version> <soma assets> [stride=<n>] [only=<ep>,..]
        [out=<dir>]
stride: silhouette on every n-th frame (default 1), carried to the frames in between ("measured" says which were).
out: write every episode there instead of the version dirs (dev runs). One json line per episode on stdout; summary.json
and provenance.json next to the parquets. CPU only (CUDA_VISIBLE_DEVICES is cleared).
"""

import json
import os
import sys
import time
from pathlib import Path

import numpy as np
from scipy.ndimage import binary_closing, uniform_filter1d
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parents[2] / "libs" / "v2d_infra")]

from t3_object_check import DILATE_PX, centroid, rasterise, visible_iou  # noqa: E402
from t3_track_check import (CLOSE_GAP, FPS, HAND_M, JUMP_M, MIN_MASK_PX, MIN_SEGMENT, MOVING_MPS,  # noqa: E402
                            SIL_CENTROID_PX, SIL_IOU, runs)

LABELS = ("ok", "unverified", "bad")
THRESHOLDS = {"min_mask_px": MIN_MASK_PX, "sil_iou": SIL_IOU, "iou_dilate_px": DILATE_PX, "sil_centroid_px": SIL_CENTROID_PX,
              "jump_m": JUMP_M, "moving_mps": MOVING_MPS, "hand_m": HAND_M, "close_gap": CLOSE_GAP, "min_segment": MIN_SEGMENT}


def silhouette(verts, faces, Tw, rot, t, s, k, obj, person):
    """One frame: (visible mask px, IoU, centroid px, 1.0 bad / 0.0 good / nan no evidence). Tw is the world pose,
    (rot, t, s) the world step's similarity (world = s * rot @ cam + t), k the intrinsics."""
    mv = obj & ~person
    px = int(mv.sum())
    if px < MIN_MASK_PX:
        return px, np.nan, np.nan, np.nan
    R_c = rot.T @ Tw[:3, :3]
    p_c = rot.T @ (Tw[:3, 3] - t) / s
    rv = rasterise(verts @ R_c.T + p_c, faces, k, *obj.shape) & ~person
    iou = visible_iou(rv, mv)
    cpx = float(np.linalg.norm(centroid(rv) - centroid(mv))) if rv.any() else np.inf
    return px, iou, cpx, float(iou < SIL_IOU or cpx > SIL_CENTROID_PX)


def motion_flags(Tw, hands, verts):
    """jump, unheld, nearest contact joint to the surface (m), smoothed speed (m/s); Tw (n, 4, 4) world poses,
    hands (n, h, 3) contact joints in the same frame, verts the mesh in its own frame."""
    p = Tw[:, :3, 3]
    jump = np.r_[0.0, np.linalg.norm(np.diff(p, axis=0), axis=1)] > JUMP_M
    local = np.einsum("nji,nhj->nhi", Tw[:, :3, :3], hands - p[:, None])  # R^T (x - t)
    hand_d = cKDTree(verts).query(local.reshape(-1, 3))[0].reshape(len(p), -1).min(1)
    speed = np.linalg.norm(np.gradient(uniform_filter1d(p, 5, axis=0, mode="nearest"), axis=0), axis=1) * FPS
    return jump, (speed > MOVING_MPS) & (hand_d > HAND_M), hand_d, speed


def label(sil, jump, unheld):
    """Per-frame label and the lost segments' frames, from the silhouette verdict (1 bad, 0 good, nan none) and flags."""
    bad = (sil == 1) | jump | unheld
    lab = np.where(bad, "bad", np.where(np.isnan(sil), "unverified", "ok"))
    closed = binary_closing(bad, structure=np.ones(CLOSE_GAP + 1)) | bad if bad.any() else bad
    lost = np.zeros(len(bad), bool)
    for a, b in runs(closed):
        if b - a >= MIN_SEGMENT:
            lost[a:b] = True
    return lab, lost


def carry(x, measured):
    """Values of unmeasured frames taken from the last measured frame (stride > 1)."""
    idx = np.maximum.accumulate(np.where(measured, np.arange(len(x)), 0))
    return x[idx]


def main() -> None:
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    import h5py
    import pyarrow as pa
    import pyarrow.parquet as pq
    from tier_guard import forbid_lower_tiers
    forbid_lower_tiers()  # Tier 3: nothing from Tier 1 or Tier 2 (Kaggle 2.8.c)
    import t3_provenance
    from soma import SOMALayer
    from soma.units import Unit
    from t3_align_check import HUMAN_COLUMNS, WORK, similarity, version_file, world_pose
    from t3_object_check import load_mesh
    from t3_track_check import episode_task
    from t3_world_probe import contact_joints, soma_cv, soma_joint_names

    args = [a for a in sys.argv[1:] if "=" not in a]
    kv = dict(a.split("=", 1) for a in sys.argv[1:] if "=" in a)
    root, sel, version, assets = Path(args[0]), Path(args[1]), args[2], args[3]
    stride = int(kv.get("stride", 1))
    only = {int(x) for x in kv.get("only", "").split(",") if x}
    out_dir = Path(kv["out"]) if "out" in kv else None
    prov = t3_provenance.stamp([root / "input", root / "runs" / version, root / "runs" / f"{version}_suspect", sel])
    metas = {m["episode_index"]: m for m in map(json.loads, (root / "input/meta/episodes_metadata.jsonl").read_text().splitlines()) if m}
    dyn = root / "runs" / f"{version}.dynamics_post.json"
    locked_runs = {r["episode"]: r["locked_runs"] for r in json.loads(dyn.read_text())} if dyn.exists() else {}
    layer = SOMALayer(data_root=assets, identity_model_type="mhr", device="cpu", output_unit=Unit.METERS,
                      enable_procedural_transforms=False)
    summary = {}
    for r in json.loads(sel.read_text()):
        ep, name, conv = r["episode_index"], r["episode"], r["convert"]
        if only and ep not in only:
            continue
        t0 = time.time()
        src = version_file(root, version, ep)
        dest = out_dir or src.parents[2] / "confidence"
        s, rot, t, k, _ = similarity(root / "runs" / conv / name)
        verts, faces = load_mesh(root / "input" / metas[ep]["mesh"])
        Tw = world_pose(root, version, ep)
        n = len(Tw)
        H = h5py.File(root / "runs" / WORK[conv] / name / "masks_k0.h5", "r")[f"episode_{ep:06d}"]
        px = np.full(n, -1, np.int64)
        iou, cpx, sil = np.full(n, np.nan), np.full(n, np.nan), np.full(n, np.nan)
        measured = np.zeros(n, bool)
        for f in range(0, n, stride):
            ok, pk = f"{f:06d}-k0.obj_rend_mask.png", f"{f:06d}-k0.person_mask.png"
            if ok not in H:
                continue
            obj = H[ok][()] > 0
            person = H[pk][()] > 0 if pk in H else np.zeros_like(obj)
            px[f], iou[f], cpx[f], sil[f] = silhouette(verts, faces, Tw[f], rot, t, s, k, obj, person)
            measured[f] = True
        if not measured.any():
            raise SystemExit(f"{name}: no mask frames in {WORK[conv]}/{name}/masks_k0.h5")
        if stride > 1:
            px, iou, cpx, sil = (carry(x, measured) for x in (px, iou, cpx, sil))
        tab = pq.read_table(src, columns=list(HUMAN_COLUMNS.values()))
        sp = {kk: np.stack(tab.column(c).to_numpy(zero_copy_only=False)).astype(np.float64) for kk, c in HUMAN_COLUMNS.items()}
        joints, _ = soma_cv(sp, layer)  # world (OpenCV), frame-0 identity and scale, as downstream
        names = soma_joint_names(layer, joints.shape[1])
        jump, unheld, hand_d, speed = motion_flags(Tw, joints[:, contact_joints(names, episode_task(root / "input", ep))], verts)
        lab, lost = label(sil, jump, unheld)
        locked = np.zeros(n, bool)
        for lr in locked_runs.get(name, []):
            locked[lr["start"]:lr["end"]] = True
        dest.mkdir(parents=True, exist_ok=True)
        table = pa.table({
            "frame_index": pa.array(np.arange(n), pa.int32()), "label": pa.array(lab.tolist(), pa.string()),
            "measured": pa.array(measured), "mask_px": pa.array(px, pa.int32()),
            "iou": pa.array(iou, pa.float32()), "centroid_px": pa.array(cpx, pa.float32()),
            "silhouette_bad": pa.array(sil == 1), "jump": pa.array(jump), "unheld": pa.array(unheld),
            "locked": pa.array(locked), "lost": pa.array(lost),
            "hand_m": pa.array(hand_d, pa.float32()), "speed_mps": pa.array(speed, pa.float32())})
        table = table.replace_schema_metadata({b"frame_confidence": json.dumps(
            {"version": version, "episode": name, "convert": conv, "stride": stride, "thresholds": THRESHOLDS}).encode()})
        pq.write_table(table, dest / f"episode_{ep:06d}.parquet")
        row = {"episode": name, "frames": n, "measured": int(measured.sum()),
               **{f"{x}_share": round(float((lab == x).mean()), 4) for x in LABELS},
               "silhouette_bad": int((sil == 1).sum()), "jump": int(jump.sum()), "unheld": int(unheld.sum()),
               "lost_fraction": round(float(lost.mean()), 4), "locked_share": round(float(locked.mean()), 4),
               "iou_p50": round(float(np.nanmedian(iou)), 4) if np.isfinite(iou).any() else None,
               "seconds": round(time.time() - t0, 1), "dir": str(dest)}
        summary[name] = row
        print(json.dumps(row), flush=True)
    for d in sorted({Path(v["dir"]) for v in summary.values()}):
        rows = {kk: {x: y for x, y in v.items() if x != "dir"} for kk, v in summary.items() if Path(v["dir"]) == d}
        (d / "summary.json").write_text(json.dumps({"version": version, "stride": stride, "thresholds": THRESHOLDS,
                                                    "episodes": rows}, indent=1))
        t3_provenance.write(d / "provenance.json", prov | {"made_by": "t3_frame_confidence.py", "from_version": version})


if __name__ == "__main__":
    main()
