"""Tier 3 world-frame probe: per episode, fit the floor plane from MoGe-2 points on a few frames and compare it
with the released ground plane read as if the released world were the exo camera's OpenCV frame.

Reads only Tier 3 permitted inputs: the exo videos, episodes_metadata.jsonl and ground_plane/*.json. No
trajectory parquet is read; any path naming tier_1 is refused.

    python moge_ground_probe.py <input_dir> <out_dir> [frames_per_episode]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np
import torch

MOGE2_MODEL_ID = "Ruicheng/moge-2-vitl-normal"
MOGE2_REVISION = "b135031bae30b5ac2ae141a0e68717795ce38340"
FLOOR_ROW_FRACTION = 0.6   # only pixels below this fraction of the image height are floor candidates
MAX_DEPTH_M = 12.0
RANSAC_ITERS = 400
RANSAC_INLIER_M = 0.02


def refuse_tier1(path: Path) -> Path:
    if "tier_1" in str(path.resolve()):
        raise SystemExit(f"refusing a Tier 1 path: {path}")
    return path


def read_frames(video: Path, count: int) -> tuple[list[np.ndarray], list[int]]:
    cap = cv2.VideoCapture(str(refuse_tier1(video)))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    indices = np.linspace(0, total - 1, count).round().astype(int).tolist()
    frames = []
    for i in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ok, bgr = cap.read()
        if not ok:
            raise RuntimeError(f"cannot read frame {i} of {video}")
        frames.append(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
    cap.release()
    return frames, indices


def fit_plane(points: np.ndarray, rng: np.random.Generator) -> tuple[np.ndarray, float, float]:
    """RANSAC then least squares. Returns (unit normal pointing to camera side, d, inlier fraction), n.x + d = 0."""
    best = None
    for _ in range(RANSAC_ITERS):
        a, b, c = points[rng.choice(len(points), 3, replace=False)]
        n = np.cross(b - a, c - a)
        norm = np.linalg.norm(n)
        if norm < 1e-9:
            continue
        n /= norm
        d = -float(n @ a)
        inliers = np.abs(points @ n + d) < RANSAC_INLIER_M
        if best is None or inliers.sum() > best.sum():
            best = inliers
    inl = points[best]
    centroid = inl.mean(axis=0)
    _, _, vt = np.linalg.svd(inl - centroid, full_matrices=False)
    n = vt[-1]
    d = -float(n @ centroid)
    if d < 0:  # orient so the camera (origin) is on the positive side
        n, d = -n, -d
    return n, d, float(best.mean())


def oriented(plane: list[float]) -> tuple[np.ndarray, float]:
    n = np.asarray(plane[:3], dtype=float)
    d = float(plane[3])
    s = np.linalg.norm(n)
    n, d = n / s, d / s
    if d < 0:
        n, d = -n, -d
    return n, d


def main() -> None:
    inp, out = refuse_tier1(Path(sys.argv[1])), Path(sys.argv[2])
    per_ep = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    out.mkdir(parents=True, exist_ok=True)
    model = MoGeModel.from_pretrained(MOGE2_MODEL_ID, revision=MOGE2_REVISION, local_files_only=True).cuda().eval()
    rng = np.random.default_rng(0)
    rows = []
    for line in open(inp / "meta" / "episodes_metadata.jsonl"):
        meta = json.loads(line)
        ep = int(meta["episode_index"])
        video = inp / "videos" / f"episode_{ep:06d}.mp4"
        released = json.loads((inp / "ground_plane" / Path(meta["ground_plane"]).name).read_text())["plane"]
        frames, indices = read_frames(video, per_ep)
        images = torch.from_numpy(np.stack(frames)).cuda().permute(0, 3, 1, 2).float().div_(255.0)
        with torch.inference_mode():
            pred = model.infer(images, resolution_level=9, force_projection=True, apply_mask=True, use_fp16=True)
        points = pred["points"].float().cpu().numpy()
        mask = pred["mask"].cpu().numpy().astype(bool)
        kn = pred["intrinsics"].float().cpu().numpy()
        h, w = points.shape[1:3]
        per_frame = []
        for k in range(len(frames)):
            p = points[k]
            sel = mask[k] & np.isfinite(p).all(-1) & (p[..., 2] > 0) & (p[..., 2] < MAX_DEPTH_M)
            sel[: int(h * FLOOR_ROW_FRACTION)] = False
            cand = p[sel]
            if len(cand) > 20000:
                cand = cand[rng.choice(len(cand), 20000, replace=False)]
            n, d, frac = fit_plane(cand, rng)
            per_frame.append({"frame": indices[k], "normal": n.round(4).tolist(), "d_m": round(d, 4), "inlier_frac": round(frac, 3),
                              "fx_px": round(float(kn[k, 0, 0] * w), 1), "fy_px": round(float(kn[k, 1, 1] * h), 1),
                              "cx_px": round(float(kn[k, 0, 2] * w), 1), "cy_px": round(float(kn[k, 1, 2] * h), 1)})
        n_est = np.mean([f["normal"] for f in per_frame], axis=0)
        n_est /= np.linalg.norm(n_est)
        d_est = float(np.median([f["d_m"] for f in per_frame]))
        n_rel, d_rel = oriented(released)
        angle = float(np.degrees(np.arccos(np.clip(n_est @ n_rel, -1, 1))))
        row = {"episode_index": ep, "sequence_id": meta["sequence_id"], "angle_deg": round(angle, 2),
               "d_moge_m": round(d_est, 3), "d_released_m": round(d_rel, 3), "d_ratio": round(d_est / d_rel, 3),
               "n_moge": n_est.round(4).tolist(), "n_released": n_rel.round(4).tolist(), "frames": per_frame}
        rows.append(row)
        print(f"ep{ep:02d} angle={angle:5.2f}deg d_moge={d_est:.3f} d_rel={d_rel:.3f} ratio={d_est / d_rel:.3f} "
              f"fx={np.median([f['fx_px'] for f in per_frame]):.0f}", flush=True)
    (out / "moge_ground_probe.json").write_text(json.dumps(rows, indent=1))


if __name__ == "__main__":
    from moge.model.v2 import MoGeModel  # only exists inside the v2d_cari4d image

    main()
