"""MoGe-2 point maps of picked frames, for SAM 3D Objects to generate the object at metric scale.

For each frame_NNNNNN.png writes <out_root>/moge_NNNNNN/points.npy (H, W, 3) float32 in the OpenCV camera
frame, NaN where MoGe has no valid point, and intrinsics.json in the toolkit's CameraIntrinsics layout. Runs
inside the v2d_cari4d image (it carries MoGe-2 at the revision CARI4D pins), so the point maps and CARI4D's
own depth come from the same model. One container launch loads the model once for all frames.

    python t3_moge_frame.py <out_root> <frame_NNNNNN.png>...
"""

import json
import sys
from pathlib import Path

import numpy as np
import torch
from PIL import Image

MOGE2_MODEL_ID = "Ruicheng/moge-2-vitl-normal"
MOGE2_REVISION = "b135031bae30b5ac2ae141a0e68717795ce38340"


def main() -> None:
    from moge.model.v2 import MoGeModel

    out_root, frames = Path(sys.argv[1]), [Path(a) for a in sys.argv[2:]]
    model = MoGeModel.from_pretrained(MOGE2_MODEL_ID, revision=MOGE2_REVISION, local_files_only=True).cuda().eval()
    for frame in frames:
        one(model, frame, out_root / ("moge_" + frame.stem.split("_")[-1]))


def one(model, frame: Path, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    rgb = np.asarray(Image.open(frame).convert("RGB"))
    h, w = rgb.shape[:2]
    image = torch.from_numpy(rgb).cuda().permute(2, 0, 1).float().div_(255.0)
    with torch.inference_mode():
        pred = model.infer(image, resolution_level=9, force_projection=True, apply_mask=True, use_fp16=True)
    points = pred["points"].float().cpu().numpy()
    valid = pred["mask"].cpu().numpy().astype(bool) & np.isfinite(points).all(-1) & (points[..., 2] > 0)
    points[~valid] = np.nan
    np.save(out / "points.npy", points.astype(np.float32))
    k = pred["intrinsics"].float().cpu().numpy()
    intr = {"fx": float(k[0, 0] * w), "fy": float(k[1, 1] * h), "cx": float(k[0, 2] * w), "cy": float(k[1, 2] * h), "width": w, "height": h}
    (out / "intrinsics.json").write_text(json.dumps(intr, indent=4))
    print(frame.name, json.dumps({"valid_fraction": round(float(valid.mean()), 3), **{key: round(v, 1) for key, v in intr.items() if key in ("fx", "cx", "cy")}}))


if __name__ == "__main__":
    main()
