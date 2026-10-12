"""Where did CARI4D lose the object? Per-frame flags and lost segments, from Tier 3 inputs and CARI4D's output only.

The episode-level gate (t3_object_check.py) judges medians, so an episode can pass while a stretch of it is lost
(ep03: median 12 cm, RMS 107 cm against the dev reference). This marks the stretches. Per frame, in the camera frame:

  - silhouette: the official mesh at CARI4D's pose vs the SAM2 object mask, person pixels removed from both
    (as t3_object_check.py, IoU of the silhouettes dilated by its DILATE_PX). Bad when the mask shows enough object and IoU < SIL_IOU or the centroids are more than
    SIL_CENTROID_PX apart. No visible mask: no evidence either way.
  - jump: the pose moves more than JUMP_M from the previous frame. Rotation is not used: on symmetric objects the
    angle about the symmetry axis is unobservable and flips frame to frame (ep03's mug: median 13 deg per frame).
  - unheld motion: the object moves faster than MOVING_MPS (smoothed) while no contact joint is within HAND_M of its
    surface. Objects in these tasks move only when a person moves them. Contact joints are the hands, plus the feet
    when the episode's task text (Tier 3 input/meta/episodes_metadata.jsonl) says foot or feet (ep13, ep29 push with
    a foot); a foot that is near the object in any other task is not taken as moving it.

Bad frames closed over gaps of CLOSE_GAP frames, runs of at least MIN_SEGMENT kept. Thresholds are set from these
definitions, not tuned against any reference; t3_world_eval.py-style measurements judge them separately.

    python t3_track_check.py <convert dir> <work dir with sam2_masks> <official mesh .glb> <soma assets> <out .json> [stride]
"""

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import binary_closing, uniform_filter1d
from scipy.spatial import cKDTree

from t3_object_check import DILATE_PX, centroid, load_mesh, rasterise, visible_iou
from t3_world_probe import FOOT_JOINTS, HUMAN_KEYS, contact_joints, soma_cv, soma_joint_names

FPS = 30.0
MIN_MASK_PX = 150
SIL_IOU = 0.3
SIL_CENTROID_PX = 40.0
JUMP_M = 0.10
MOVING_MPS = 0.15
HAND_M = 0.25
CLOSE_GAP = 15
MIN_SEGMENT = 8


def episode_task(inp: Path, ep: int) -> str:
    rows = [json.loads(line) for line in (inp / "meta" / "episodes_metadata.jsonl").read_text().splitlines() if line.strip()]
    return next(m["task"] for m in rows if m["episode_index"] == ep)


def runs(mask: np.ndarray) -> list[tuple[int, int]]:
    edges = np.flatnonzero(np.diff(np.r_[0, mask.astype(int), 0]))
    return [(int(a), int(b)) for a, b in zip(edges[::2], edges[1::2])]


def main() -> None:
    from soma import SOMALayer
    from soma.units import Unit

    conv, work, mesh_path, assets, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4], Path(sys.argv[5])
    stride = int(sys.argv[6]) if len(sys.argv) > 6 else 2
    oc = np.load(conv / "object_cam.npz")
    poses = oc["T_cam_glb"].astype(np.float64)
    k = np.asarray(oc["intrinsics"], np.float64)
    if k.shape != (3, 3):
        raise SystemExit(f"intrinsics shape {k.shape}, want (3, 3)")
    n = len(poses)
    verts, faces = load_mesh(mesh_path)

    # silhouette on every stride-th frame, carried to the frames in between
    sil = np.full(n, np.nan)  # 1 bad, 0 good, nan no evidence
    iou = np.full(n, np.nan)
    cpx = np.full(n, np.nan)
    for i in range(0, n, stride):
        om, pm = work / "sam2_masks" / "1" / f"{i:06d}.png", work / "sam2_masks" / "0" / f"{i:06d}.png"
        if not om.exists():
            continue
        obj = np.asarray(Image.open(om).convert("L")) > 0
        person = np.asarray(Image.open(pm).convert("L")) > 0 if pm.exists() else np.zeros_like(obj)
        mv = obj & ~person
        if mv.sum() < MIN_MASK_PX:
            continue
        h, w = obj.shape
        t = poses[i]
        rv = rasterise(verts @ t[:3, :3].T + t[:3, 3], faces, k, h, w) & ~person
        iou[i] = visible_iou(rv, mv)
        cpx[i] = float(np.linalg.norm(centroid(rv) - centroid(mv))) if rv.any() else np.inf
        sil[i] = float(iou[i] < SIL_IOU or cpx[i] > SIL_CENTROID_PX)
    for i in range(n):
        if np.isnan(sil[i]) and i % stride:
            j = i - i % stride
            sil[i] = sil[j]

    # jumps
    dt = np.r_[0.0, np.linalg.norm(np.diff(poses[:, :3, 3], axis=0), axis=1)]
    jump = dt > JUMP_M

    # unheld motion: contact joints vs the mesh surface, in the object's frame
    layer = SOMALayer(data_root=assets, identity_model_type="mhr", device="cpu", output_unit=Unit.METERS,
                      enable_procedural_transforms=False)
    sp = dict(np.load(conv / "soma_params.npz", allow_pickle=True))
    joints, _ = soma_cv({kk: sp[kk][:n] for kk in HUMAN_KEYS}, layer)
    names = soma_joint_names(layer, joints.shape[1])
    task = episode_task(mesh_path.parents[2], int(conv.name[2:4]))  # <input>/mesh/<obj>/<obj>.glb
    contact_idx = contact_joints(names, task)
    hands = joints[:, contact_idx]  # (n, h, 3) camera frame
    tree = cKDTree(verts)
    local = np.einsum("nji,nhj->nhi", poses[:, :3, :3], hands - poses[:, None, :3, 3])  # R^T (p - t)
    hand_d = tree.query(local.reshape(-1, 3))[0].reshape(n, -1).min(1)
    speed = np.linalg.norm(np.gradient(uniform_filter1d(poses[:, :3, 3], 5, axis=0, mode="nearest"), axis=0), axis=1) * FPS
    unheld = (speed > MOVING_MPS) & (hand_d > HAND_M)

    bad = (sil == 1) | jump | unheld
    closed = binary_closing(bad, structure=np.ones(CLOSE_GAP + 1)) | bad if bad.any() else bad
    segs = [(a, b) for a, b in runs(closed) if b - a >= MIN_SEGMENT]
    lost = np.zeros(n, bool)
    for a, b in segs:
        lost[a:b] = True
    seen = ~np.isnan(sil)
    report = {"episode": conv.name, "frames": n, "stride": stride,
              "contact": "hands+feet" if any(names[i] in FOOT_JOINTS for i in contact_idx) else "hands",
              "contact_joints": len(contact_idx),
              "thresholds": {"min_mask_px": MIN_MASK_PX, "sil_iou": SIL_IOU, "iou_dilate_px": DILATE_PX, "sil_centroid_px": SIL_CENTROID_PX, "jump_m": JUMP_M, "moving_mps": MOVING_MPS, "hand_m": HAND_M, "close_gap": CLOSE_GAP, "min_segment": MIN_SEGMENT},
              "silhouette_frames": int(seen.sum()), "silhouette_bad": int((sil == 1).sum()), "jump_frames": int(jump.sum()),
              "unheld_frames": int(unheld.sum()), "lost_frames": int(lost.sum()), "lost_fraction": round(float(lost.mean()), 4),
              "segments": [{"start": a, "end": b, "frames": b - a, "silhouette_bad": int((sil[a:b] == 1).sum()),
                            "silhouette_seen": int(seen[a:b].sum()), "jump": int(jump[a:b].sum()), "unheld": int(unheld[a:b].sum())}
                           for a, b in segs]}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1))
    np.savez_compressed(out.with_suffix(".npz"), lost=lost, sil=sil, iou=iou, centroid_px=cpx, jump=jump, unheld=unheld,
                        hand_d=hand_d, speed=speed)
    print(json.dumps({kk: v for kk, v in report.items() if kk not in ("segments", "thresholds", "contact_joints")} | {"segments": [(s["start"], s["end"]) for s in report["segments"]]}))


if __name__ == "__main__":
    main()
