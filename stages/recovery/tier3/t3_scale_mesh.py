"""Turn a SAM 3D Objects result (generated with a MoGe-2 point map) into the metric mesh CARI4D reads, and
check it against the frame it came from.

The SAM3D transform maps the exported object-space mesh into the OpenCV camera frame (scale -> rotate ->
translate). The metric mesh is the object-space mesh times that scale, centred. Two self-consistency checks,
both against inputs SAM3D already saw, so they catch a broken scale or a broken convention, not a wrong shape:
  - the posed mesh projects onto the object mask (box IoU of the projected vertices vs the mask box);
  - the posed mesh's median depth matches the MoGe depth inside the mask.

    python t3_scale_mesh.py --sam3d <dir with object.glb, transform.json> --frame-dir <dir with mask_*.png, pick.json>
                            --moge <dir with points.npy, intrinsics.json> --out <dir> [--frame N]
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image
from v2d.common.datatypes import Transform3d

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "libs" / "v2d_infra"))
from tier_guard import forbid_tier1

MIN_BOX_IOU = 0.5
MAX_DEPTH_RATIO_ERR = 0.15


def box(xs: np.ndarray, ys: np.ndarray) -> tuple[float, float, float, float]:
    return float(xs.min()), float(ys.min()), float(xs.max()), float(ys.max())


def box_iou(a, b) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    area = lambda r: (r[2] - r[0]) * (r[3] - r[1])
    return inter / (area(a) + area(b) - inter + 1e-9)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sam3d", required=True)
    ap.add_argument("--frame-dir", required=True)
    ap.add_argument("--moge", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--frame", type=int, default=None, help="frame the SAM3D run used; default pick.json's frame_index")
    a = ap.parse_args()
    forbid_tier1()
    sam3d, frame_dir, moge, out = map(Path, (a.sam3d, a.frame_dir, a.moge, a.out))
    out.mkdir(parents=True, exist_ok=True)

    mesh = trimesh.load(sam3d / "object.glb", force="mesh")
    T = Transform3d.from_dict(json.loads((sam3d / "transform.json").read_text()))
    M = T.to_matrix()
    posed = mesh.vertices @ M[:3, :3].T + M[:3, 3]

    intr = json.loads((moge / "intrinsics.json").read_text())
    z = posed[:, 2]
    front = z > 1e-6
    u = intr["fx"] * posed[front, 0] / z[front] + intr["cx"]
    v = intr["fy"] * posed[front, 1] / z[front] + intr["cy"]

    idx = a.frame if a.frame is not None else json.loads((frame_dir / "pick.json").read_text())["frame_index"]
    mask = np.asarray(Image.open(frame_dir / f"mask_{idx:06d}.png").convert("L")) > 0
    my, mx = np.nonzero(mask)
    points = np.load(moge / "points.npy")
    moge_z = points[..., 2][mask]
    moge_z = moge_z[np.isfinite(moge_z)]

    iou = box_iou(box(u, v), box(mx, my)) if front.any() else 0.0
    depth_ratio = float(np.median(z) / np.median(moge_z)) if len(moge_z) else float("nan")

    scaled = mesh.copy()
    scaled.vertices = mesh.vertices * np.asarray(T.scale)[None, :]  # per-axis, in case SAM3D's scale is anisotropic
    scaled.apply_translation(-scaled.bounding_box.centroid)
    scaled.export(out / "object_scaled.glb")

    problems = []
    if iou < MIN_BOX_IOU:
        problems.append(f"posed mesh projects off the mask (box IoU {iou:.2f})")
    if not abs(depth_ratio - 1.0) <= MAX_DEPTH_RATIO_ERR:
        problems.append(f"posed mesh depth / MoGe depth = {depth_ratio:.2f}")
    report = {"frame_index": idx, "scale": [round(s, 5) for s in T.scale], "extents_m": scaled.extents.round(4).tolist(),
              "projected_box_iou": round(iou, 3), "depth_ratio": round(depth_ratio, 3), "posed_median_z_m": round(float(np.median(z)), 3),
              "ok": not problems, "why": "; ".join(problems)}
    (out / "scale_report.json").write_text(json.dumps(report, indent=1))
    print(json.dumps(report))


if __name__ == "__main__":
    main()
