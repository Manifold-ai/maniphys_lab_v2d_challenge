"""Diagnosis sheet for one CARI4D episode: what went wrong, mask or pose?

Eight frames spread over the clip, each half size, with the SAM2 object mask filled red, the SAM2 person mask outlined
blue and CARI4D's object pose (full-resolution official mesh, as t3_object_check.py) outlined green; label: frame,
visible IoU, area ratio, centroid offset from object_check.json when that frame was checked. Under the frames, the
per-frame visible IoU over the whole clip (from object_check.json; grey where the frame had too few visible pixels).
Reading it:
  - green on the object, red partial or on something else -> the mask is wrong, the pose may be fine;
  - red on the object, green elsewhere or turned -> CARI4D lost the pose;
  - both wrong -> the mask misled the tracker.
Runs in the v2d_cari4d image (cv2, torch, trimesh), CPU.

    python t3_diag_sheet.py <cari4d episode dir> <work dir with sam2_masks> <official mesh .glb> <video> <object_check.json> <out .png>
"""

import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from t3_object_check import load_mesh, rasterise  # noqa: E402

N_FRAMES = 8
STRIP_H = 120


def frame_rgb(video: Path, i: int) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-noautorotate", "-i", str(video), "-vf", f"select=eq(n\\,{i})", "-frames:v", "1",
                          "-f", "image2pipe", "-vcodec", "png", "-"], check=True, capture_output=True).stdout
    return cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)


def main() -> None:
    ep_dir, work, mesh_path, video, check_path, out = (Path(a) for a in sys.argv[1:7])
    bundle = torch.load(ep_dir / "inference" / "refined.pth", map_location="cpu", weights_only=False)
    poses = np.asarray(bundle["pr"]["pose_abs"], np.float64)
    export = json.loads((ep_dir / "export" / ep_dir.name / "wild_export.json").read_text())
    s2a = np.asarray(export["source_object_mesh_to_aligned_transform"], np.float64)
    ki = export["intrinsics"]
    k = np.asarray(ki, np.float64).reshape(3, 3) if not isinstance(ki, dict) else np.array(
        [[ki["fx"], 0, ki["cx"]], [0, ki["fy"], ki["cy"]], [0, 0, 1]])
    verts, faces = load_mesh(mesh_path)
    check = json.loads(check_path.read_text())
    rows = {r["frame"]: r for r in check.get("rows", [])}
    n = len(poses)
    picks = sorted({round(j * (n - 1) / (N_FRAMES - 1)) for j in range(N_FRAMES)})
    picks = [min(rows, key=lambda f: abs(f - p)) if rows else p for p in picks]  # snap to checked frames, so labels have numbers
    tiles = []
    for i in picks:
        img = frame_rgb(video, i)
        h, w = img.shape[:2]
        om, pm = work / "sam2_masks" / "1" / f"{i:06d}.png", work / "sam2_masks" / "0" / f"{i:06d}.png"
        obj = cv2.imread(str(om), cv2.IMREAD_GRAYSCALE) > 0 if om.exists() else np.zeros((h, w), bool)
        person = cv2.imread(str(pm), cv2.IMREAD_GRAYSCALE) > 0 if pm.exists() else np.zeros((h, w), bool)
        t = poses[i] @ s2a
        rend = rasterise(verts @ t[:3, :3].T + t[:3, 3], faces, k, h, w)
        img[obj] = (img[obj] * 0.45 + np.array([0, 0, 255]) * 0.55).astype(np.uint8)
        for m, colour in ((person, (255, 120, 0)), (rend, (0, 255, 0))):
            edge = cv2.Canny(m.astype(np.uint8) * 255, 50, 150) > 0
            img[cv2.dilate(edge.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0] = colour
        r = rows.get(i)
        text = f"f{i}" + (f"  IoU {r['iou_visible']:.2f}  area {r['area_ratio']:.2f}  off {r['centroid_px']:.0f}px" if r else "  (not checked)")
        small = cv2.resize(img, (w // 2, h // 2), interpolation=cv2.INTER_AREA)
        cv2.rectangle(small, (0, 0), (w // 2, 30), (0, 0, 0), -1)
        cv2.putText(small, text, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
        tiles.append(small)
    while len(tiles) % 4:
        tiles.append(np.zeros_like(tiles[0]))
    grid = np.vstack([np.hstack(tiles[r: r + 4]) for r in range(0, len(tiles), 4)])
    strip = np.full((STRIP_H, grid.shape[1], 3), 255, np.uint8)
    for f, r in rows.items():
        x = int(f / max(n - 1, 1) * (grid.shape[1] - 1))
        y = int((1 - r["iou_visible"]) * (STRIP_H - 21)) + 20
        cv2.line(strip, (x, STRIP_H - 1), (x, y), (0, 160, 0) if r["iou_visible"] >= 0.5 else (0, 0, 220), 2)
    for x, f in ((int(p / max(n - 1, 1) * (grid.shape[1] - 1)), p) for p in picks):
        cv2.line(strip, (x, 0), (x, 16), (0, 0, 0), 2)
    cv2.putText(strip, f"visible IoU per frame (green >= 0.5, red < 0.5), {n} frames; {check.get('why', 'gate ok')}", (8, 14),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
    cv2.imwrite(str(out), np.vstack([grid, strip]))


if __name__ == "__main__":
    main()
