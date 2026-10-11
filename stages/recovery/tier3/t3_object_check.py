"""How well does a CARI4D object trajectory explain the video? Silhouette checks against the SAM2 masks.

For sampled frames, the official mesh is placed at CARI4D's pose (T_cam<-glb = pose_abs @ S2A, see
prepare_mhr_wild_export.py) and rasterised with CARI4D's own intrinsics. Person pixels are removed from both the
render and the object mask, so a hand in front of the object does not count against the pose. Per frame:

  - iou_visible: IoU of render and object mask outside the person mask, both dilated by DILATE_PX first (visible_iou);
  - area_ratio: visible render area / visible mask area. A pose that sits too close to the camera renders too
    big (ratio > 1); with a correct mesh scale, distance scales as sqrt(ratio), so depth_factor = sqrt(ratio)
    estimates how much farther the object should be;
  - centroid_px: offset between the two visible centroids.

No ground truth is read; every input is a Tier 3 input or CARI4D's output. Runs in the v2d_cari4d image on CPU.

The check is relative to CARI4D's intrinsics: a focal length that is off by x% moves the object x% in depth and
the silhouette still fits. It tests the pose given fx, not fx itself. T3_CHECK_POSE_SCALE (default 1) scales the
pose translations, for proving the check reacts to a wrong depth.

    python t3_object_check.py <cari4d episode dir> <work dir with sam2_masks> <official mesh .glb> <out dir> [stride]
"""

import json
import os
import sys
from pathlib import Path

import cv2
import numpy as np
import torch
import trimesh
from PIL import Image

MIN_VISIBLE_PX = 400
#: Quality gate on the medians over checked frames. ep20/ep00/ep05 sit at IoU 0.88/0.76/0.81, depth factor
#: 1.00/0.93/0.92, centroid 3-5 px; ep01's lost track sits at IoU 0.08, centroid 47 px.
GATE_IOU = 0.5
GATE_DEPTH = (0.8, 1.25)
GATE_CENTROID_PX = 25.0
#: Both silhouettes are dilated by this many pixels before the IoU. Plain IoU punishes thin objects for offsets that
#: do not matter: a cane ~20 px wide shifted by 3 px loses a third of its overlap, a box 170 px wide does not notice.
#: At 5 px (10-12, every 6th frame) the references keep their places: good ep20/ep00/ep05 0.89/0.79/0.92 ->
#: 0.90/0.84/0.93, lost ep01/ep10 0.03/0.16 -> 0.07/0.19; thin ep19 (every-frame registration) 0.31 -> 0.55 while
#: its centroid offset stays 15 px, ep28 0.21 -> 0.43 (centroid 35 px: partly off for real), ep04 0.08 -> 0.18 (lost).
#: At 8 px the lost references start to rise (ep01's share of frames under 0.3: 0.99 -> 0.93).
DILATE_PX = 5


def load_mesh(path: Path) -> tuple[np.ndarray, np.ndarray]:
    # Full resolution on purpose. Quadric decimation to 20k faces ate thin parts: on the same pose the skateboard
    # covered 0.62 of its mask decimated and 0.90 at full resolution, the round table 0.71 vs 0.93, and both episodes
    # failed the gate on the renderer, not on the pose.
    mesh = trimesh.load(path, force="mesh", process=False)
    return np.asarray(mesh.vertices, np.float64), np.asarray(mesh.faces, np.int64)


def rasterise(verts_cam: np.ndarray, faces: np.ndarray, k: np.ndarray, h: int, w: int) -> np.ndarray:
    z = verts_cam[:, 2]
    if (z <= 1e-3).any():
        return np.zeros((h, w), bool)
    uv = (verts_cam[:, :2] / z[:, None]) * [k[0, 0], k[1, 1]] + [k[0, 2], k[1, 2]]
    out = np.zeros((h, w), np.uint8)
    cv2.fillPoly(out, list(np.round(uv[faces] * 4).astype(np.int32)), 1, lineType=cv2.LINE_8, shift=2)
    return out.astype(bool)


def visible_iou(rv: np.ndarray, mv: np.ndarray, k: int = DILATE_PX) -> float:
    """IoU of two silhouettes after dilating both by k px (see DILATE_PX)."""
    if k:
        ker = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * k + 1, 2 * k + 1))
        rv, mv = cv2.dilate(rv.astype(np.uint8), ker) > 0, cv2.dilate(mv.astype(np.uint8), ker) > 0
    return float((rv & mv).sum()) / max(1.0, float((rv | mv).sum()))


def centroid(m: np.ndarray) -> np.ndarray:
    ys, xs = np.nonzero(m)
    return np.array([xs.mean(), ys.mean()])


def main() -> None:
    ep_dir, work, mesh_path, out = (Path(a) for a in sys.argv[1:5])
    stride = int(sys.argv[5]) if len(sys.argv) > 5 else 3
    out.mkdir(parents=True, exist_ok=True)
    bundle = torch.load(ep_dir / "inference" / "refined.pth", map_location="cpu", weights_only=False)
    poses = np.asarray(bundle["pr"]["pose_abs"], np.float64)
    pose_scale = float(os.environ.get("T3_CHECK_POSE_SCALE", "1"))
    poses[:, :3, 3] *= pose_scale
    seq = ep_dir.name
    export = json.loads((ep_dir / "export" / seq / "wild_export.json").read_text())
    s2a = np.asarray(export["source_object_mesh_to_aligned_transform"], np.float64)
    k = np.asarray(export["intrinsics"], np.float64).reshape(3, 3) if not isinstance(export["intrinsics"], dict) else np.array(
        [[export["intrinsics"]["fx"], 0, export["intrinsics"]["cx"]], [0, export["intrinsics"]["fy"], export["intrinsics"]["cy"]], [0, 0, 1]])
    verts, faces = load_mesh(mesh_path)
    rows, worst = [], []
    for i in range(0, len(poses), stride):
        om, pm = work / "sam2_masks" / "1" / f"{i:06d}.png", work / "sam2_masks" / "0" / f"{i:06d}.png"
        if not om.exists():
            continue
        obj = np.asarray(Image.open(om).convert("L")) > 0
        person = np.asarray(Image.open(pm).convert("L")) > 0 if pm.exists() else np.zeros_like(obj)
        h, w = obj.shape
        t = poses[i] @ s2a
        rend = rasterise(verts @ t[:3, :3].T + t[:3, 3], faces, k, h, w)
        rv, mv = rend & ~person, obj & ~person
        if rv.sum() < MIN_VISIBLE_PX or mv.sum() < MIN_VISIBLE_PX:
            continue
        ratio = float(rv.sum()) / float(mv.sum())
        row = {"frame": i, "iou_visible": round(visible_iou(rv, mv), 4), "area_ratio": round(ratio, 4), "depth_factor": round(ratio**0.5, 4),
               "centroid_px": round(float(np.linalg.norm(centroid(rv) - centroid(mv))), 1), "z_m": round(float(t[2, 3]), 4),
               "person_overlap": round(float((obj & person).sum()) / float(obj.sum() + 1), 3)}
        rows.append(row)
        worst.append((row["iou_visible"], i, rend, obj))
    def summary(sel):
        if not sel:
            return None
        keys = ("iou_visible", "area_ratio", "depth_factor", "centroid_px")
        return {k_: [round(float(np.percentile([r[k_] for r in sel], p)), 4) for p in (10, 50, 90)] for k_ in keys} | {"n": len(sel)}
    clear = [r for r in rows if r["person_overlap"] < 0.05]
    problems = []
    if rows:
        med = {k_: float(np.median([r[k_] for r in rows])) for k_ in ("iou_visible", "depth_factor", "centroid_px")}
        if med["iou_visible"] < GATE_IOU:
            problems.append(f"median visible IoU {med['iou_visible']:.2f} < {GATE_IOU}")
        if not GATE_DEPTH[0] <= med["depth_factor"] <= GATE_DEPTH[1]:
            problems.append(f"median depth factor {med['depth_factor']:.2f} outside {GATE_DEPTH}")
        if med["centroid_px"] > GATE_CENTROID_PX:
            problems.append(f"median centroid offset {med['centroid_px']:.1f} px > {GATE_CENTROID_PX}")
    else:
        problems.append("no frame with enough visible object pixels")
    report = {"episode": seq, "ok": not problems, "why": "; ".join(problems),
              "stride": stride, "pose_scale": pose_scale, "frames_checked": len(rows), "fx": float(k[0, 0]),
              "all_p10_p50_p90": summary(rows), "unoccluded_p10_p50_p90": summary(clear), "rows": rows}
    (out / "object_check.json").write_text(json.dumps(report, indent=1))
    worst.sort(key=lambda x: x[0])
    for iou, i, rend, obj in worst[:3]:
        cap = cv2.VideoCapture(str(next(work.glob("episode_*.0.color.mp4"))))
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ok, frame = cap.read()
        if not ok:
            continue
        frame[obj] = (frame[obj] * 0.5 + np.array([0, 0, 255]) * 0.5).astype(np.uint8)
        edges = cv2.Canny(rend.astype(np.uint8) * 255, 50, 150) > 0
        frame[cv2.dilate(edges.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0] = (0, 255, 0)
        cv2.imwrite(str(out / f"worst_{i:06d}_iou{iou:.2f}.jpg"), frame)
    print(json.dumps({k_: v for k_, v in report.items() if k_ != "rows"}))


if __name__ == "__main__":
    main()
